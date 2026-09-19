# -*- coding: utf-8 -*-
"""프로젝트 2: AI Model Router — 난이도에 따라 모델을 고르고 절감액을 잰다."""
import random
import sys
import time
from collections import Counter

sys.path.insert(0, ".")
from _common import (LLM, LLM_FRONTIER, LLM_SMALL, require_jev, require_llm, warmup_jev)

require_jev()
require_llm()
from openai import OpenAI
from typesafe_sdk import Noul, Score, TypeSafeClient

oa = OpenAI()

MODELS = {"fast": LLM_SMALL, "balanced": LLM, "strong": LLM_FRONTIER}

# 여러분의 계약 단가로 채우세요 (100만 토큰당). 비워두면 절감액이 0으로 나옵니다.
PRICES = {name: {"in": 0.0, "out": 0.0} for name in MODELS.values()}
JEV_COST_PER_CALL = 0.0

ROUTER_QUESTIONS = {
    "difficulty": Score(criteria=[
        "정해진 절차나 사실 하나로 답할 수 있음",
        "몇 가지 정보를 종합해 설명해야 함",
        "여러 단계의 추론이나 전문 지식이 필요함",
    ]),
    "sensitive": Noul(
        instructions="답변이 틀리면 금전적 또는 법적 손해가 발생할 수 있는가?",
        criteria={"true": "환불, 계약, 개인정보, 법적 사안이 걸려 있다",
                  "false": "일반적인 안내나 정보 제공이다"}),
}

QUESTIONS = [
    "비밀번호는 어디서 바꾸나요?",
    "무료 플랜에서 API 호출은 하루 몇 건까지인가요?",
    "저희 회사는 직원 200명이고 SSO가 필요한데, 어떤 플랜을 어떻게 구성해야 할까요?",
    "환불 규정이 정확히 어떻게 되나요? 계약서와 다른 것 같습니다.",
    "웹훅이 중복 호출되는 원인을 단계별로 분석해주세요.",
    "영업시간이 어떻게 되나요?",
]


def pick_tier(answers) -> str:
    """정책. 모델에게 '어느 모델을 쓸까'를 묻지 않는다."""
    difficulty = answers.scores["difficulty"].score
    trust = answers.scores["difficulty"].confidence
    sensitive = answers.nouls["sensitive"].noul

    if sensitive >= 0.7:
        return "strong"       # 민감하면 난이도와 무관
    if trust < 0.6:
        return "balanced"     # 난이도 판정 자체가 애매하면 중간
    if difficulty >= 1.5:
        return "strong"
    if difficulty >= 0.7:
        return "balanced"
    return "fast"


def route_and_answer(question, jev, llm):
    t0 = time.perf_counter()
    judged = jev.system_one(state=question, questions=ROUTER_QUESTIONS)
    judge_ms = (time.perf_counter() - t0) * 1000

    tier = pick_tier(judged)
    t1 = time.perf_counter()
    resp = llm.chat.completions.create(model=MODELS[tier],
                                       messages=[{"role": "user", "content": question}])
    gen_ms = (time.perf_counter() - t1) * 1000

    return {"question": question, "tier": tier, "model": MODELS[tier],
            "difficulty": round(judged.scores["difficulty"].score, 2),
            "difficulty_confidence": round(judged.scores["difficulty"].confidence, 2),
            "sensitive": round(judged.nouls["sensitive"].noul, 2),
            "answer": resp.choices[0].message.content,
            "in_tokens": resp.usage.prompt_tokens,
            "out_tokens": resp.usage.completion_tokens,
            "judge_ms": round(judge_ms), "gen_ms": round(gen_ms)}


def survey(questions, jev):
    """라우터를 만들기 전에 트래픽의 난이도 분포부터 본다."""
    buckets = Counter()
    for q in questions:
        d = jev.system_one(state=q, questions=ROUTER_QUESTIONS).scores["difficulty"].score
        buckets["easy" if d < 0.7 else "medium" if d < 1.5 else "hard"] += 1
    return buckets


def cost_of(entry, model=None):
    p = PRICES[model or entry["model"]]
    return entry["in_tokens"] / 1e6 * p["in"] + entry["out_tokens"] / 1e6 * p["out"]


def savings_report(log):
    actual = sum(cost_of(e) for e in log)
    judging = len(log) * JEV_COST_PER_CALL
    baseline = sum(cost_of(e, MODELS["strong"]) for e in log)
    total = actual + judging
    return {
        "건수": len(log),
        "라우팅 적용": round(total, 4),
        "생성 비용": round(actual, 4),
        "판단 비용": round(judging, 4),
        "전량 strong": round(baseline, 4),
        "절감액": round(baseline - total, 4),
        "절감률": f"{(1 - total / baseline):.1%}" if baseline else "단가 미설정",
    }


def audit(log, jev, llm, sample_rate=0.34):
    """싼 모델로 보낸 건 일부를 strong으로 다시 돌려 비교한다."""
    cheap = [e for e in log if e["tier"] != "strong"]
    if not cheap:
        return {"표본": 0, "불일치": 0}
    sample = random.sample(cheap, max(1, int(len(cheap) * sample_rate)))

    findings = []
    for e in sample:
        strong = llm.chat.completions.create(
            model=MODELS["strong"],
            messages=[{"role": "user", "content": e["question"]}],
        ).choices[0].message.content

        same = jev.system_one(
            state={"질문": e["question"], "답변 A": e["answer"], "답변 B": strong},
            questions={"same": Noul(
                instructions="두 답변이 실질적으로 같은 내용을 말하고 있는가?",
                criteria={"true": "핵심 내용과 결론이 같다. 표현 차이는 무방하다",
                          "false": "사실이나 결론이 다르거나, 한쪽이 중요한 내용을 빠뜨렸다"})},
        ).nouls["same"].noul

        if same < 0.5:
            findings.append({"question": e["question"], "tier": e["tier"],
                             "agreement": round(same, 2)})
    return {"표본": len(sample), "불일치": len(findings), "상세": findings}


def main():
    with TypeSafeClient() as jev:
        warmup_jev(jev, ROUTER_QUESTIONS["sensitive"])

        print("[사전 조사] 난이도 분포")
        print(f"  {dict(survey(QUESTIONS, jev))}")
        print("  easy 비율이 낮으면 라우터를 만들지 마세요. 판단 비용만 늘어납니다.\n")

        log = [route_and_answer(q, jev, oa) for q in QUESTIONS]

        print(f"{'등급':10} {'난이도':>7} {'확신':>6} {'민감':>6} {'판단ms':>8} "
              f"{'생성ms':>8}  질문")
        for e in log:
            print(f"{e['tier']:10} {e['difficulty']:7.2f} "
                  f"{e['difficulty_confidence']:6.2f} {e['sensitive']:6.2f} "
                  f"{e['judge_ms']:8d} {e['gen_ms']:8d}  {e['question'][:34]}")

        print(f"\n등급별 분포: {dict(Counter(e['tier'] for e in log))}")
        print(f"절감 리포트: {savings_report(log)}")
        print("  (PRICES 를 채워야 의미 있는 숫자가 나옵니다)")
        print(f"\n품질 감사: {audit(log, jev, oa)}")


if __name__ == "__main__":
    main()
