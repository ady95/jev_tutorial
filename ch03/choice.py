# -*- coding: utf-8 -*-
"""03-1 실습: Choice — 후보 설명이 답을 바꾸고, 확률과 선택 빈도는 다르다."""
import statistics
import sys
from collections import Counter

sys.path.insert(0, ".")
from _common import require_jev, warmup_jev

require_jev()
from typesafe_sdk import Choice, TypeSafeClient

Q = "쓰던 요금제가 저한테 안 맞는 것 같아요. 어떻게 하죠?"

BARE = Choice(criteria={"billing": None, "technical": None, "sales": None, "other": None})
DESC = Choice(criteria={
    "billing": "요금 조정, 청구, 환불",
    "technical": "오류와 장애",
    "sales": "다른 상품 추천, 업그레이드 상담",
    "other": "기타",
})
N = 20


def show(label, answer):
    probs = {k: round(v, 3) for k, v in
             sorted(answer.probabilities.items(), key=lambda kv: -kv[1])}
    print(f"  {label}: {answer.choice}  conf={answer.confidence:.2f}  {probs}")


def main():
    with TypeSafeClient() as client:
        warmup_jev(client, BARE)

        print(f"문의: {Q}\n")
        print("[1] 후보 설명 유무 비교")
        for label, q in [("설명 없음", BARE), ("설명 있음", DESC)]:
            show(label, client.system_one(state=Q, questions={"d": q}).choices["d"])

        print(f"\n[2] 같은 호출 {N}회 — 확률은 안정적인데 선택은 흔들리는가")
        picks, probs, confs = [], [], []
        for _ in range(N):
            a = client.system_one(state=Q, questions={"d": DESC}).choices["d"]
            picks.append(a.choice)
            probs.append(a.probabilities.get("billing", 0.0))
            confs.append(a.confidence)

        print(f"  선택 분포        {dict(Counter(picks))}")
        print(f"  billing 확률     평균 {statistics.mean(probs):.3f}  "
              f"최소 {min(probs):.2f}  최대 {max(probs):.2f}  "
              f"표준편차 {statistics.pstdev(probs):.3f}")
        print(f"  confidence       평균 {statistics.mean(confs):.3f}")
        print(f"\n  경험적 billing 비율 {picks.count('billing')/N:.2f} "
              f"vs 반환 확률 평균 {statistics.mean(probs):.2f}")
        print("\n  choice는 probabilities의 argmax입니다. 0.5 근처에서 미세한 흔들림이")
        print("  선택을 뒤집으므로, 선택 빈도는 정답률과 무관합니다.")
        print("  => 같은 입력을 여러 번 불러 다수결하지 마세요.")


if __name__ == "__main__":
    main()
