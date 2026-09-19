# -*- coding: utf-8 -*-
"""03-4 실습: 질문을 늘려도 지연시간이 늘지 않는가.

이 책의 핵심 주장 중 하나입니다. 여러분 환경에서도 재현되는지 확인하세요.
"""
import statistics
import sys
import time
from collections import Counter

sys.path.insert(0, ".")
from _common import require_jev, warmup_jev
from dataset.inquiries import DEPARTMENTS

require_jev()
from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

Q = "쓰던 요금제가 저한테 안 맞는 것 같아요. 어떻게 하죠?"
DEPT = Choice(criteria=DEPARTMENTS)

QSETS = {
    1: {"d": DEPT},
    3: {"d": DEPT,
        "refund": Noul(instructions="환불 요구인가?"),
        "urg": Score(criteria=["급하지 않음", "보통", "급함", "매우 급함"])},
    6: {"d": DEPT,
        "refund": Noul(instructions="환불 요구인가?"),
        "urg": Score(criteria=["급하지 않음", "보통", "급함", "매우 급함"]),
        "spam": Noul(instructions="스팸인가?"),
        "human": Noul(instructions="사람이 검토해야 하는가?"),
        "sentiment": Score(criteria=["차분함", "약간 불만", "화남", "매우 화남"])},
}
REPS = 5
N = 20


def main():
    with TypeSafeClient() as client:
        warmup_jev(client, DEPT)

        print(f"[1] 질문 개수별 지연시간 (각 {REPS}회 중앙값)\n")
        print(f"{'질문 수':>7} {'중앙값':>9} {'입력 토큰':>10}")
        for k, qs in QSETS.items():
            times, tok = [], 0
            for _ in range(REPS):
                t0 = time.perf_counter()
                r = client.system_one(state=Q, questions=qs)
                times.append((time.perf_counter() - t0) * 1000)
                tok = r.usage.input_tokens
            print(f"{k:7d} {statistics.median(times):8.0f}ms {tok:10d}")

        print("\n순차 호출이라면 질문 6개는 6배 시간이 듭니다.")
        print("한 번에 던지면 그대로입니다. 입력 토큰만 늘어납니다.\n")

        print(f"[2] 질문을 묶으면 판단이 흔들리는가 (각 {N}회)\n")
        for label, qs in [("단독 질문", QSETS[1]), ("3개 동시", QSETS[3])]:
            picks = [client.system_one(state=Q, questions=qs).choices["d"].choice
                     for _ in range(N)]
            print(f"  {label:10} {dict(Counter(picks))}")

        print("\n두 분포가 비슷하면 질문을 묶어도 간섭이 없다는 뜻입니다.")
        print("(LLM은 같은 실험에서 단독 20/20, 3개 묶음 18/20으로 흔들렸습니다)")


if __name__ == "__main__":
    main()
