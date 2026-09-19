# -*- coding: utf-8 -*-
"""02-2 실습: 첫 번째 Jev 프로그램.

프롬프트도, 출력 형식 지시도, 파싱도 없습니다.
"""
import sys
import time

sys.path.insert(0, ".")
from _common import require_jev
from dataset.inquiries import DEPARTMENTS

require_jev()
from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

TEXT = "결제가 두 번 됐습니다. 빨리 환불해주세요."

QUESTIONS = {
    "department": Choice(criteria=DEPARTMENTS),
    "refund": Noul(
        instructions="고객이 환불이나 결제 취소를 요구하고 있는가?",
        criteria={"true": "환불이나 결제 취소를 실제로 요청하고 있다",
                  "false": "가능 여부만 묻거나, 원하지 않거나, 무관하다"}),
    "urgency": Score(criteria=["급하지 않음", "보통", "급함", "매우 급함"]),
}


def main():
    with TypeSafeClient() as client:
        t0 = time.perf_counter()
        r = client.system_one(state=TEXT, questions=QUESTIONS)
        ms = (time.perf_counter() - t0) * 1000

    print(f"문의: {TEXT}")
    print(f"모델: {r.model}   지연시간: {ms:.0f}ms (첫 호출이라 느립니다)")
    print(f"토큰: 입력 {r.usage.input_tokens} / 출력 {r.usage.output_tokens}\n")

    d = r.choices["department"]
    print(f"department  {d.choice}  confidence {d.confidence:.2f}")
    for k, v in sorted(d.probabilities.items(), key=lambda kv: -kv[1]):
        print(f"            {k:12} {v:.4f}")

    n = r.nouls["refund"]
    print(f"\nrefund      {n.noul:.2f}   (confidence 필드는 없습니다)")
    print(f"            0.5로부터의 거리로 환산한 확신도 {abs(n.noul - 0.5) * 2:.2f}")

    s = r.scores["urgency"]
    print(f"\nurgency     {s.score:.2f}  confidence {s.confidence:.2f}")
    print(f"            legend {s.legend}")
    probs = {int(k): round(v, 2) for k, v in s.probabilities.items()}
    print(f"            probs  {probs}")

    expected = sum(int(k) * v for k, v in s.probabilities.items())
    print(f"\n기대값 검산: {expected:.2f} (score {s.score:.2f}와 같아야 합니다)")
    print(f"확률 합 검산: choice {sum(d.probabilities.values()):.4f} / "
          f"score {sum(s.probabilities.values()):.4f}")


if __name__ == "__main__":
    main()
