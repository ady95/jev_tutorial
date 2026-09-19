# -*- coding: utf-8 -*-
"""05-4 실습: 작은 판단을 조합해 우선순위를 만든다.

핵심은 조합 로직이 코드에 있다는 것입니다. 가중치를 바꿔도 모델을 다시 부르지 않습니다.
"""
import sys

sys.path.insert(0, ".")
from _common import require_jev, warmup_jev

require_jev()
from typesafe_sdk import Noul, Score, TypeSafeClient

FACTORS = {
    "severity": Score(criteria=["불편하지만 사용 가능", "일부 기능 불가", "서비스 전체 불가"]),
    "scope": Score(criteria=["한 사용자", "일부 사용자", "전체 사용자"]),
    "sentiment": Score(criteria=["차분함", "약간 불만", "화남", "매우 화남"]),
    "churn_risk": Noul(instructions="이 고객이 서비스를 떠날 위험이 있는가?"),
    "legal_threat": Noul(instructions="법적 조치나 신고를 언급하고 있는가?"),
}

WEIGHTS = {"severity": 0.4, "scope": 0.3, "sentiment": 0.1, "churn_risk": 0.2}
LEVELS = {"severity": 2, "scope": 2, "sentiment": 3}   # 각 Score의 최대 단계

CASES = [
    "결제가 안 돼서 서비스를 아예 못 쓰고 있습니다. 전 직원이 마비 상태예요.",
    "버튼 색이 잘 안 보이네요. 다음에 개선해주시면 좋겠습니다.",
    "이런 식이면 소비자원에 신고하고 계약 해지하겠습니다.",
    "로그인이 가끔 느린데 크게 불편하진 않습니다.",
]


def judge(text, client):
    return client.system_one(state=text, questions=FACTORS)


def compose(r):
    """모델 판단을 우선순위로 바꾼다. 이 함수가 정책이다."""
    norm = {k: r.scores[k].score / LEVELS[k] for k in LEVELS}
    norm["churn_risk"] = r.nouls["churn_risk"].noul
    score = sum(WEIGHTS[k] * norm[k] for k in WEIGHTS)

    # 판단 네 개를 합치면 불확실성도 합쳐진다. 가장 약한 고리를 본다.
    trust = min([a.confidence for a in r.scores.values()]
                + [abs(a.noul - 0.5) * 2 for a in r.nouls.values()])

    if r.nouls["legal_threat"].noul >= 0.7:
        level = "P1"
    elif trust < 0.6:
        level = "REVIEW"
    elif score >= 0.70:
        level = "P1"
    elif score >= 0.45:
        level = "P2"
    else:
        level = "P3"

    return {"level": level, "score": round(score, 3), "trust": round(trust, 3),
            "factors": {k: round(v, 3) for k, v in norm.items()}}


def main():
    with TypeSafeClient() as client:
        warmup_jev(client, FACTORS["churn_risk"])
        for text in CASES:
            out = compose(judge(text, client))
            print(f"[{out['level']:6}] score={out['score']:.3f} trust={out['trust']:.2f}")
            print(f"          {out['factors']}")
            print(f"          {text[:48]}\n")

    print("가중치를 바꿔 다시 돌려보세요. 같은 판단으로 다른 정책을 만들 수 있습니다.")
    print("정책만 바꾸는 것이라면 저장된 판단으로 재계산하면 됩니다 (API 호출 0회).")


if __name__ == "__main__":
    main()
