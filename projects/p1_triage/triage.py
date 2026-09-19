# -*- coding: utf-8 -*-
"""프로젝트 1: 고객문의 자동 분류 시스템."""
import io
import json
import os
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

sys.path.insert(0, ".")
from _common import require_jev, warmup_jev
from dataset.inquiries import DEPARTMENTS, TEXTS

require_jev()
from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

QUESTIONS = {
    "department": Choice(criteria=DEPARTMENTS),
    "refund": Noul(instructions="고객이 환불이나 결제 취소를 요구하고 있는가?",
                   criteria={"true": "환불이나 결제 취소를 실제로 요청하고 있다",
                             "false": "가능 여부만 묻거나, 원하지 않거나, 무관하다"}),
    "spam": Noul(instructions="광고나 스팸 메시지인가?"),
    "urgency": Score(criteria=["급하지 않음", "보통", "급함", "매우 급함"]),
    "sentiment": Score(criteria=["차분함", "약간 불만", "화남", "매우 화남"]),
}

# 정책 상수. 근거는 책 04-3의 Risk-Coverage 실측.
AUTO_CONFIDENCE = 0.90     # 이 값에서 자동화 62% / 측정 오류율 0%
SPAM_BLOCK = 0.95
URGENT_ESCALATE = 2.5
ANGRY_ESCALATE = 2.5
POLICY_VERSION = "v1"


@dataclass
class Ticket:
    text: str
    lane: str = ""
    department: str = ""
    confidence: float = 0.0
    alternatives: dict = field(default_factory=dict)
    refund: float = 0.0
    spam: float = 0.0
    urgency: float = 0.0
    sentiment: float = 0.0
    reason: str = ""
    latency_ms: float = 0.0
    model: str = ""
    policy_version: str = POLICY_VERSION
    at: str = ""


def judge(text, client) -> Ticket:
    """판단만 한다. 정책을 모른다."""
    t0 = time.perf_counter()
    r = client.system_one(state=text, questions=QUESTIONS)
    ms = (time.perf_counter() - t0) * 1000
    d = r.choices["department"]
    return Ticket(
        text=text, department=d.choice, confidence=round(d.confidence, 3),
        alternatives={k: round(v, 3) for k, v in
                      sorted(d.probabilities.items(), key=lambda kv: -kv[1])[:3]},
        refund=round(r.nouls["refund"].noul, 3),
        spam=round(r.nouls["spam"].noul, 3),
        urgency=round(r.scores["urgency"].score, 2),
        sentiment=round(r.scores["sentiment"].score, 2),
        latency_ms=round(ms), model=r.model,
        at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def apply_policy(t: Ticket) -> Ticket:
    """판단값으로 처리 레인을 정한다. 순서가 곧 정책이다."""
    if t.spam >= SPAM_BLOCK:
        t.lane, t.reason = "quarantine", "스팸으로 판정"
    elif t.urgency >= URGENT_ESCALATE or t.sentiment >= ANGRY_ESCALATE:
        t.lane, t.reason = "escalate", "긴급하거나 고객이 격앙됨"
    elif t.refund >= 0.9:
        t.lane, t.reason = "refund_flow", "환불 요청으로 판정"
    elif t.confidence >= AUTO_CONFIDENCE:
        t.lane, t.reason = "auto_route", f"{t.department} 자동 배정"
    else:
        t.lane, t.reason = "review", f"분류 확신 부족 ({t.confidence})"
    return t


def run(inquiries):
    out = []
    with TypeSafeClient() as client:
        warmup_jev(client, QUESTIONS["spam"])
        for text in inquiries:
            out.append(apply_policy(judge(text, client)))
    return out


def report(tickets):
    n = len(tickets)
    print(f"\n{'레인':14} {'건수':>5} {'비율':>8}")
    for lane, c in Counter(t.lane for t in tickets).most_common():
        print(f"{lane:14} {c:5d} {c/n:8.1%}")

    auto = [t for t in tickets if t.lane == "auto_route"]
    if auto:
        depts = Counter(t.department for t in auto)
        print("\n자동 배정 " + str(len(auto)) + "건: "
              + ", ".join(f"{k} {v}" for k, v in depts.most_common()))
    print(f"\n평균 지연시간 {sum(t.latency_ms for t in tickets)/n:.0f}ms   "
          f"모델 {tickets[0].model}")


def main():
    tickets = run(TEXTS)

    print(f"{'레인':13} {'부서':10} {'conf':>5} {'환불':>5} {'긴급':>5} {'감정':>5}  문의")
    for t in tickets[:14]:
        print(f"{t.lane:13} {t.department:10} {t.confidence:5.2f} {t.refund:5.2f} "
              f"{t.urgency:5.2f} {t.sentiment:5.2f}  {t.text[:30]}")
    print("  ...")
    report(tickets)

    os.makedirs("out", exist_ok=True)
    json.dump([asdict(t) for t in tickets],
              io.open("out/tickets.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("\n판단 로그 저장 -> out/tickets.json")
    print("정책만 바꿔 재현하려면: python projects/p1_triage/replay.py")


if __name__ == "__main__":
    main()
