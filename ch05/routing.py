# -*- coding: utf-8 -*-
"""05-2, 05-3 실습: Intent Routing과 Confidence 게이트."""
import sys
from collections import defaultdict

sys.path.insert(0, ".")
from _common import require_jev, warmup_jev
from dataset.inquiries import DEPARTMENTS, TEXTS

require_jev()
from typesafe_sdk import Choice, Noul, TypeSafeClient

QUESTIONS = {
    "route": Choice(criteria=DEPARTMENTS),
    "spam": Noul(instructions="광고나 스팸 메시지인가?"),
}

AUTO = 0.90      # 04-3 Risk-Coverage 실측 근거
REVIEW = 0.60
SPAM_BLOCK = 0.95


def run(inquiries):
    routed, review, human, spam_box = defaultdict(list), [], [], []

    with TypeSafeClient() as client:
        warmup_jev(client, QUESTIONS["spam"])
        for text in inquiries:
            r = client.system_one(state=text, questions=QUESTIONS)
            route = r.choices["route"]
            top2 = dict(sorted(route.probabilities.items(), key=lambda kv: -kv[1])[:2])

            if r.nouls["spam"].noul >= SPAM_BLOCK:
                spam_box.append(text)
            elif route.confidence >= AUTO:
                routed[route.choice].append(text)
            elif route.confidence >= REVIEW:
                # 실무에서는 이 구간을 LLM 재검토로 흡수합니다 (ch06/hybrid.py)
                review.append({"text": text, "suggested": route.choice,
                               "confidence": round(route.confidence, 2),
                               "alternatives": {k: round(v, 2) for k, v in top2.items()}})
            else:
                human.append({"text": text, "suggested": route.choice,
                              "confidence": round(route.confidence, 2),
                              "alternatives": {k: round(v, 2) for k, v in top2.items()}})

    return routed, review, human, spam_box


def main():
    routed, review, human, spam_box = run(TEXTS)
    n = len(TEXTS)
    auto = sum(len(v) for v in routed.values())

    print(f"{'레인':12} {'건수':>5} {'비율':>8}")
    for name, cnt in [("자동 라우팅", auto), ("AI 재검토", len(review)),
                      ("사람 검토", len(human)), ("스팸 격리", len(spam_box))]:
        print(f"{name:12} {cnt:5d} {cnt/n:8.1%}")

    print("\n부서별 자동 배정:")
    for dept, items in sorted(routed.items(), key=lambda kv: -len(kv[1])):
        print(f"  {dept:12} {len(items):3d}건")

    print("\n사람 검토 큐 (모델 근거를 함께 넘깁니다):")
    for item in human[:5]:
        print(f"  conf={item['confidence']:.2f} 제안={item['suggested']:10} "
              f"대안={item['alternatives']}  {item['text'][:30]}")


if __name__ == "__main__":
    main()
