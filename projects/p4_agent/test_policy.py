# -*- coding: utf-8 -*-
"""정책은 순수 함수라 평범한 단위 테스트로 검증됩니다.

pytest 없이도 실행됩니다:  python projects/p4_agent/test_policy.py

행동 어휘 (policy.py 기준):
  execute   바로 실행
  approve   사람 승인을 받고 실행
  block     실행하지 않음
  escalate  사람에게 넘김
  ask_user  되물음
  finish    답변 작성으로 넘어감
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from policy import Judgment, decide


def test_read_only_always_executes():
    j = Judgment(tool="search_docs", confidence=0.99, reversible=0.74, impact=0.02)
    assert decide(j)[0] == "execute"


def test_reversible_small_change_executes():
    """되돌릴 수 있고 영향이 작으면 사람을 부르지 않습니다."""
    j = Judgment(tool="update_profile", confidence=0.95, reversible=0.70, impact=0.97)
    assert decide(j)[0] == "execute"


def test_destructive_blocked():
    j = Judgment(tool="delete_account", confidence=0.99, reversible=0.19, impact=2.98)
    assert decide(j)[0] == "block"


def test_high_impact_blocked():
    """도구 목록에 없어도 impact가 높으면 막습니다."""
    j = Judgment(tool="wipe_cache", confidence=0.95, reversible=0.2, impact=2.7)
    assert decide(j)[0] == "block"


def test_irreversible_external_needs_approval_not_block():
    """되돌릴 수 없다는 이유만으로 차단하면 메일 한 통도 못 보내는 Agent가 됩니다."""
    j = Judgment(tool="send_email", confidence=0.95, reversible=0.17, impact=1.98)
    action, _ = decide(j)
    assert action == "approve"


def test_small_refund_needs_approval():
    j = Judgment(tool="issue_refund", confidence=0.95, reversible=0.26, impact=1.96)
    action, reason = decide(j, {"amount": 5000})
    assert action == "approve"
    assert "한도 초과" not in reason      # 한도 때문이 아니라 되돌릴 수 없어서


def test_large_refund_flagged_by_amount():
    """금액 비교는 모델이 아니라 코드가 합니다."""
    j = Judgment(tool="issue_refund", confidence=0.95, reversible=0.26, impact=1.97)
    action, reason = decide(j, {"amount": 3_000_000})
    assert action == "approve"
    assert "한도 초과" in reason          # 사유가 금액이어야 한다


def test_low_confidence_escalates():
    j = Judgment(tool="issue_refund", confidence=0.41, reversible=0.5, impact=1.0)
    assert decide(j)[0] == "escalate"


def test_missing_info_asks_user():
    j = Judgment(tool="get_order", confidence=0.95, ready=False)
    assert decide(j)[0] == "ask_user"


def test_done_finishes():
    """done이 다른 모든 조건보다 우선합니다."""
    j = Judgment(tool="delete_account", confidence=0.2, done=True, impact=3.0)
    assert decide(j)[0] == "finish"


def test_model_requested_escalation():
    j = Judgment(tool="escalate", confidence=0.95)
    assert decide(j)[0] == "escalate"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  OK   {t.__name__}")
        except AssertionError:
            failed += 1
            print(f"  FAIL {t.__name__}")
    print(f"\n{len(tests) - failed}/{len(tests)} 통과")
    sys.exit(1 if failed else 0)
