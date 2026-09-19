# -*- coding: utf-8 -*-
"""프로젝트 3: RAG 품질검사 파이프라인."""
import asyncio
import sys

sys.path.insert(0, ".")
from _common import require_jev

require_jev()
from typesafe_sdk import AsyncTypeSafeClient, Noul, Score

# 데모용 문서 모음. 여러분의 벡터 스토어로 교체하세요.
CORPUS = [
    "환불은 결제일로부터 7일 이내에 신청해야 하며, 7일이 지나면 부분 환불만 가능합니다.",
    "환불 신청은 마이페이지 > 주문내역에서 할 수 있습니다.",
    "무료 체험은 14일간 제공되며 기간 내 해지 시 과금되지 않습니다.",
    "결제 수단은 신용카드, 계좌이체, 간편결제를 지원합니다.",
    "연간 구독 해지 시 남은 기간은 일할 계산하여 30일 이내에 환급됩니다.",
    "7일 이내 환불 요청 건은 전액 환불되며 영업일 기준 3일 내 처리됩니다.",
    "비밀번호는 로그인 화면의 '비밀번호 찾기'에서 재설정할 수 있습니다.",
    "API 호출 한도는 무료 플랜 기준 하루 1,000건입니다.",
]

RELEVANCE = {
    "relevant": Noul(
        instructions="이 문서가 질문에 답하는 데 직접 도움이 되는가?",
        criteria={"true": "질문이 묻는 정보를 실제로 담고 있다",
                  "false": "같은 주제이지만 질문이 묻는 내용은 없다"}),
    "answerable": Score(criteria=["전혀 답할 수 없음", "일부만 답할 수 있음", "완전히 답할 수 있음"]),
}

VERIFY = {
    "supported": Noul(
        instructions="답변의 내용이 제공된 문서로 뒷받침되는가?",
        criteria={"true": "문서에 있는 내용만으로 구성되어 있다",
                  "false": "문서에 없는 사실이나 숫자가 들어 있다"}),
    "relevant": Noul(instructions="답변이 질문에 실제로 답하고 있는가?"),
    "complete": Score(criteria=["질문에 답하지 못함", "일부만 답함", "충분히 답함"]),
}

RELEVANCE_FLOOR = 0.5
ANSWERABLE_FLOOR = 1.0
KEEP = 3
SUPPORTED_FLOOR = 0.7


def search(query, k=8):
    """데모용. 실제로는 벡터 검색기를 붙이세요."""
    return CORPUS[:k]


def llm_generate(query, context):
    """데모용. 실제로는 LLM을 호출하세요."""
    return f"{context.splitlines()[0]} (문서 기준)"


async def judge_docs(query, docs, client):
    tasks = [client.system_one(state={"질문": query, "검색된 문서": d}, questions=RELEVANCE)
             for d in docs]
    results = await asyncio.gather(*tasks)
    return [{"doc": d,
             "relevant": r.nouls["relevant"].noul,
             "answerable": r.scores["answerable"].score}
            for d, r in zip(docs, results)]


def filter_and_rank(judged):
    kept = sorted((j for j in judged if j["relevant"] >= RELEVANCE_FLOOR),
                  key=lambda j: -j["relevant"])[:KEEP]
    best = max((j["answerable"] for j in kept), default=0.0)
    return kept, best


async def answer(query, client):
    docs = search(query)
    judged = await judge_docs(query, docs, client)
    kept, answerable = filter_and_rank(judged)

    if not kept or answerable < ANSWERABLE_FLOOR:
        return {"answer": None, "reason": "관련 문서를 찾지 못했습니다",
                "answerable": round(answerable, 2)}

    context = "\n\n".join(j["doc"] for j in kept)
    draft = llm_generate(query, context)

    v = await client.system_one(
        state={"질문": query, "제공된 문서": context, "작성된 답변": draft},
        questions=VERIFY)
    supported = v.nouls["supported"].noul
    relevant = v.nouls["relevant"].noul
    complete = v.scores["complete"].score

    if supported < SUPPORTED_FLOOR:
        return {"answer": None, "reason": "근거 없는 내용이 포함됨",
                "supported": round(supported, 2), "draft": draft}
    if relevant < 0.7 or complete < 1.0:
        return {"answer": draft, "warning": "질문에 충분히 답하지 못했을 수 있음",
                "complete": round(complete, 2)}

    return {"answer": draft, "sources": [j["doc"] for j in kept],
            "supported": round(supported, 2)}


async def run():
    queries = [
        "환불은 며칠 안에 신청해야 하나요?",
        "비밀번호를 어떻게 바꾸나요?",
        "해외 결제도 되나요?",        # 문서에 없는 질문
    ]

    async with AsyncTypeSafeClient() as client:
        await client.system_one(state="워밍업", questions={"_": RELEVANCE["relevant"]})
        for q in queries:
            r = await answer(q, client)
            print(f"\n질문: {q}")
            if r.get("answer"):
                print(f"  답변: {r['answer'][:60]}")
                print(f"  supported={r.get('supported')}  "
                      f"{r.get('warning', '')}")
                print(f"  근거 {len(r.get('sources', []))}건")
            else:
                print(f"  답변하지 않음 — {r['reason']}")

    print("\n문서에 없는 질문에 '모르겠습니다'로 답하는 것이 이 파이프라인의 핵심입니다.")


if __name__ == "__main__":
    asyncio.run(run())
