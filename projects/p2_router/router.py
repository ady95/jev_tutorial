# -*- coding: utf-8 -*-
"""프로젝트 2: AI Model Router — 난이도에 따라 모델을 고르고 절감액을 잰다.

책 08-2 의 코드와 같습니다. 등급은 둘(fast = 하위 티어, strong = 프런티어)이고,
절감액의 기준선은 감사에서 프런티어로 실제 다시 돌린 기록(shadow)의 토큰으로 계산합니다.
싼 모델의 토큰에 프런티어 단가를 곱하지 않습니다 — 모델마다 출력 길이가 달라서
실제로는 비용이 늘었는데 절감으로 보일 수 있습니다.
"""
import random
import sys
import time
import uuid
from collections import Counter

sys.path.insert(0, ".")
from _common import LLM_FRONTIER, LLM_SMALL, require_jev, require_llm, warmup_jev

require_jev()
require_llm()
from openai import OpenAI
from typesafe_sdk import Noul, Score, TypeSafeClient

MODELS = {
    "fast": LLM_SMALL,        # 하위 티어 (.env 의 OPENAI_MODEL_SMALL)
    "strong": LLM_FRONTIER,   # 프런티어 (.env 의 OPENAI_MODEL_FRONTIER)
}

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
        return "strong"        # 민감하면 난이도와 무관
    if trust < 0.6:
        return "strong"        # 난이도 판정이 애매하면 안전한 쪽으로
    if difficulty >= 0.7:
        return "strong"
    return "fast"


def route_and_answer(question, jev, llm):
    t0 = time.perf_counter()
    judged = jev.system_one(state=question, questions=ROUTER_QUESTIONS)
    judge_ms = (time.perf_counter() - t0) * 1000

    tier = pick_tier(judged)
    model = MODELS[tier]

    t1 = time.perf_counter()
    resp = llm.chat.completions.create(
        model=model, messages=[{"role": "user", "content": question}])
    gen_ms = (time.perf_counter() - t1) * 1000

    return {
        "request_id": uuid.uuid4().hex,          # 같은 질문이 여러 번 와도 요청마다 다르다
        "question": question,
        "tier": tier,
        "model": model,
        "difficulty": round(judged.scores["difficulty"].score, 2),
        "difficulty_confidence": round(judged.scores["difficulty"].confidence, 2),
        "sensitive": round(judged.nouls["sensitive"].noul, 2),
        "answer": resp.choices[0].message.content,
        "in_tokens": resp.usage.prompt_tokens,
        "out_tokens": resp.usage.completion_tokens,
        "judge_ms": round(judge_ms),
        "gen_ms": round(gen_ms),
    }


def survey(questions, jev):
    """라우터를 만들기 전에 트래픽의 난이도 분포부터 본다."""
    buckets = Counter()
    for q in questions:
        d = jev.system_one(state=q, questions=ROUTER_QUESTIONS).scores["difficulty"].score
        buckets["easy" if d < 0.7 else "medium" if d < 1.5 else "hard"] += 1
    return buckets


def cost_of(entry):
    """단가표는 모델 이름으로 찾고, 그 기록에 남은 토큰으로만 계산한다."""
    p = PRICES[entry["model"]]
    return entry["in_tokens"] / 1e6 * p["in"] + entry["out_tokens"] / 1e6 * p["out"]


def savings_report(log, shadow):
    """shadow: 싼 모델로 간 요청 일부를 프런티어로도 돌린 기록 (audit 에서 나온다).

    요청은 request_id 로 짝짓는다. 질문 문자열로 짝지으면 같은 질문이 두 번 왔을 때 겹친다.
    """
    cheap = {e["request_id"]: e for e in log if e["tier"] != "strong"}
    judging = len(log) * JEV_COST_PER_CALL           # 판단은 모든 요청에 붙는다
    report = {"전체 건수": len(log), "싼 모델로 간 건": len(cheap), "판단 비용": judging}
    if not cheap:                                    # 아낀 것 없이 판단 비용만 남는다
        report.update({"라우팅 절감 추정 (감사 비용 제외)": -judging,
                       "감사 비용": 0.0, "감사 포함 순절감": -judging})
        return report

    pairs = [(cheap[s["request_id"]], s) for s in shadow if s["request_id"] in cheap]
    report["그중 프런티어로도 돌린 표본"] = len(pairs)
    if not pairs:
        report["라우팅 절감 추정 (감사 비용 제외)"] = "shadow 표본이 없어 추정 불가"
        return report

    routed = sum(cost_of(e) for e, _ in pairs)
    frontier = sum(cost_of(s) for _, s in pairs)
    per_item = (frontier - routed) / len(pairs)      # 싼 모델로 보낸 한 건당 아낀 돈
    routing = per_item * len(cheap) - judging
    # 감사가 실제로 쓴 돈: 프런티어 재호출 + 두 답변 비교 판단
    audit_cost = sum(cost_of(s) for s in shadow) + len(shadow) * JEV_COST_PER_CALL

    report.update({
        "표본에서 싼 모델의 비용 비율": f"{routed / frontier:.1%}" if frontier else "-",
        "라우팅 절감 추정 (감사 비용 제외)": routing,
        "감사 비용": audit_cost,
        "감사 포함 순절감": routing - audit_cost,
    })
    return report                                    # 반올림은 출력할 때만 한다


def show_report(report):
    for k, v in report.items():
        print(f"  {k}: {v:.6g}" if isinstance(v, float) else f"  {k}: {v}")


def audit(log, llm, jev, sample_rate=0.05):
    """싼 모델로 보낸 건 일부를 프런티어로 다시 돌려 비교한다.

    그때의 토큰 기록(shadow)이 savings_report 의 비용 기준선이 된다.
    """
    cheap = [e for e in log if e["tier"] != "strong"]
    sample = random.sample(cheap, max(1, int(len(cheap) * sample_rate))) if cheap else []

    findings, shadow = [], []
    for e in sample:
        resp = llm.chat.completions.create(
            model=MODELS["strong"],
            messages=[{"role": "user", "content": e["question"]}],
        )
        strong = resp.choices[0].message.content
        shadow.append({"request_id": e["request_id"],      # 원래 요청과 짝지을 키
                       "question": e["question"], "tier": "strong",
                       "model": MODELS["strong"],
                       "in_tokens": resp.usage.prompt_tokens,
                       "out_tokens": resp.usage.completion_tokens})

        # 두 답변이 실질적으로 다른지 판단시킨다
        cmp = jev.system_one(
            state={"질문": e["question"], "답변 A": e["answer"], "답변 B": strong},
            questions={"same": Noul(
                instructions="두 답변이 실질적으로 같은 내용을 말하고 있는가?",
                criteria={"true": "핵심 내용과 결론이 같다. 표현 차이는 무방하다",
                          "false": "사실이나 결론이 다르거나, 한쪽이 중요한 내용을 빠뜨렸다"})},
        ).nouls["same"].noul

        if cmp < 0.5:
            findings.append({"question": e["question"], "tier": e["tier"],
                             "cheap": e["answer"], "strong": strong,
                             "agreement": round(cmp, 2)})
    return {"표본": len(sample), "불일치": len(findings), "상세": findings, "shadow": shadow}


def main():
    if MODELS["fast"] == MODELS["strong"]:
        print("주의: fast 와 strong 이 같은 모델입니다. .env 에 OPENAI_MODEL_SMALL 과 "
              "OPENAI_MODEL_FRONTIER 를 따로 지정하세요.\n")

    llm = OpenAI()
    with TypeSafeClient() as jev:
        warmup_jev(jev, ROUTER_QUESTIONS["sensitive"])

        print("[사전 조사] 난이도 분포")
        print(f"  {dict(survey(QUESTIONS, jev))}")
        print("  easy 비율이 낮으면 라우터를 만들지 마세요. 판단 비용만 늘어납니다.\n")

        log = [route_and_answer(q, jev, llm) for q in QUESTIONS]

        print(f"{'등급':10} {'난이도':>7} {'확신':>6} {'민감':>6} {'판단ms':>8} "
              f"{'생성ms':>8}  질문")
        for e in log:
            print(f"{e['tier']:10} {e['difficulty']:7.2f} "
                  f"{e['difficulty_confidence']:6.2f} {e['sensitive']:6.2f} "
                  f"{e['judge_ms']:8d} {e['gen_ms']:8d}  {e['question'][:34]}")
        print(f"\n등급별 분포: {dict(Counter(e['tier'] for e in log))}")

        # 예제는 6건뿐이라 표본 비율을 높였다. 실제 트래픽에서는 5% 안팎이면 된다
        report = audit(log, llm, jev, sample_rate=0.5)     # 감사가 비용 기준선을 만든다
        print(f"\n품질 감사: { {k: v for k, v in report.items() if k != 'shadow'} }")
        print("절감 리포트:")
        show_report(savings_report(log, report["shadow"]))
        print("  (PRICES 를 채워야 의미 있는 숫자가 나옵니다)")


if __name__ == "__main__":
    main()
