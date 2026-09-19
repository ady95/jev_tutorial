# -*- coding: utf-8 -*-
"""03-3 실습: Score — 돌아오는 값은 정수가 아니라 기대값이다."""
import sys

sys.path.insert(0, ".")
from _common import require_jev, warmup_jev

require_jev()
from typesafe_sdk import Score, TypeSafeClient

SENTIMENT = Score(criteria=["차분함", "약간 불만", "화남", "매우 화남"])

CASES = [
    "정말 감사합니다 덕분에 해결됐어요",
    "언제쯤 처리되나요?",
    "며칠째 답이 없네요. 확인 부탁드립니다",
    "이런 서비스는 처음입니다. 당장 해지하겠습니다",
]


def main():
    with TypeSafeClient() as client:
        warmup_jev(client, SENTIMENT)

        print(f"{'score':>6} {'반올림':>7} {'conf':>6}  확률 분포 / 문의")
        for text in CASES:
            a = client.system_one(state=text, questions={"s": SENTIMENT}).scores["s"]
            probs = {int(k): round(v, 2) for k, v in a.probabilities.items() if v > 0.005}
            print(f"{a.score:6.2f} {round(a.score):7d} {a.confidence:6.2f}  {probs}")
            print(f"{'':22}{text}")

            expected = sum(int(k) * v for k, v in a.probabilities.items())
            assert abs(expected - a.score) < 0.02, "기대값 검산 실패"

        print("\n기대값 검산 통과 (score = sum(단계 x 확률))")
        print("\n반올림하기 전에 confidence를 보세요.")
        print("conf가 0.5 근처면 반올림으로 절반의 가능성을 버리는 셈입니다.")


if __name__ == "__main__":
    main()
