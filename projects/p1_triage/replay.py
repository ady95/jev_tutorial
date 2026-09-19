# -*- coding: utf-8 -*-
"""저장된 판단에 다른 정책을 적용해본다. API 호출 없음.

임계값을 바꾸면 몇 건이 더 자동화되는지 호출 한 번 없이 계산할 수 있습니다.
"""
import io
import json
import os
import sys
from collections import Counter

sys.path.insert(0, ".")
sys.path.insert(0, os.path.dirname(__file__))
from triage import Ticket, apply_policy

SRC = "out/tickets.json"


def replay(tickets, auto_confidence):
    """자동 라우팅 임계값만 바꿔 다시 계산한다."""
    import triage
    original = triage.AUTO_CONFIDENCE
    triage.AUTO_CONFIDENCE = auto_confidence
    try:
        return [apply_policy(Ticket(**{k: v for k, v in t.items()
                                       if k not in ("lane", "reason")}))
                for t in tickets]
    finally:
        triage.AUTO_CONFIDENCE = original


def main():
    if not os.path.exists(SRC):
        sys.exit(f"{SRC} 가 없습니다. 먼저 python projects/p1_triage/triage.py 를 실행하세요.")

    raw = json.load(io.open(SRC, encoding="utf-8"))
    n = len(raw)

    print(f"저장된 판단 {n}건으로 임계값을 바꿔 재현합니다 (API 호출 0회)\n")
    print(f"{'임계값':>7} {'자동':>6} {'검토':>6} {'기타':>6} {'자동화율':>9}")
    for th in (0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99):
        lanes = Counter(t.lane for t in replay(raw, th))
        auto = lanes.get("auto_route", 0)
        review = lanes.get("review", 0)
        other = n - auto - review
        print(f"  {th:5.2f} {auto:6d} {review:6d} {other:6d} {auto/n:9.1%}")

    print("\n정답 라벨이 있다면 오류율도 함께 계산해 Risk-Coverage 표를 만들 수 있습니다.")
    print("판단을 로그에 남겨두면 정책은 언제든 실험할 수 있습니다.")


if __name__ == "__main__":
    main()
