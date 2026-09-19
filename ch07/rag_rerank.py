# -*- coding: utf-8 -*-
"""07-1 실습: 검색 결과를 판단으로 걸러내고 재랭킹한다.

벡터 검색은 '비슷한' 문서를 찾고, 판단은 '답이 되는' 문서를 찾습니다.
"""
import asyncio
import sys
import time

sys.path.insert(0, ".")
from _common import require_jev

require_jev()
from typesafe_sdk import AsyncTypeSafeClient, Noul, Score, TypeSafeClient

QUERY = "환불은 며칠 안에 신청해야 하나요?"

# 벡터 검색 결과라고 가정합니다. (문서, 실제로 질문에 답이 되는가)
DOCS = [
    ("환불은 결제일로부터 7일 이내에 신청해야 하며, 7일이 지나면 부분 환불만 가능합니다.", True),
    ("환불 신청은 마이페이지 > 주문내역에서 할 수 있습니다.", False),
    ("무료 체험은 14일간 제공되며 기간 내 해지 시 과금되지 않습니다.", False),
    ("결제 수단은 신용카드, 계좌이체, 간편결제를 지원합니다.", False),
    ("연간 구독 해지 시 남은 기간은 일할 계산하여 30일 이내에 환급됩니다.", False),
    ("7일 이내 환불 요청 건은 전액 환불되며 영업일 기준 3일 내 처리됩니다.", True),
]

RELEVANCE = {
    "relevant": Noul(
        instructions="이 문서가 질문에 답하는 데 직접 도움이 되는가?",
        criteria={"true": "질문이 묻는 정보를 실제로 담고 있다",
                  "false": "같은 주제이지만 질문이 묻는 내용은 없다"}),
    "answerable": Score(criteria=["전혀 답할 수 없음", "일부만 답할 수 있음", "완전히 답할 수 있음"]),
}

RELEVANCE_FLOOR = 0.5
KEEP = 3


async def judge_all(query, docs, client):
    """문서 판정은 서로 독립적이라 병렬 처리에 완벽하게 맞습니다."""
    tasks = [client.system_one(state={"질문": query, "검색된 문서": d}, questions=RELEVANCE)
             for d in docs]
    return await asyncio.gather(*tasks)


async def run():
    texts = [d for d, _ in DOCS]

    async with AsyncTypeSafeClient() as client:
        await client.system_one(state="워밍업",
                                questions={"_": RELEVANCE["relevant"]})
        t0 = time.perf_counter()
        results = await judge_all(QUERY, texts, client)
        ms = (time.perf_counter() - t0) * 1000

    judged = [{"doc": d, "truth": truth,
               "relevant": r.nouls["relevant"].noul,
               "answerable": r.scores["answerable"].score}
              for (d, truth), r in zip(DOCS, results)]

    print(f"질문: {QUERY}\n")
    print(f"{'rel':>5} {'ans':>5} {'정답':>5}  문서")
    for j in judged:
        print(f"{j['relevant']:5.2f} {j['answerable']:5.2f} "
              f"{'관련' if j['truth'] else '무관':>5}  {j['doc'][:44]}")

    hit = sum((j["relevant"] >= RELEVANCE_FLOOR) == j["truth"] for j in judged)
    print(f"\n판정 정확도 {hit}/{len(judged)}   "
          f"{len(texts)}건 동시 판정에 {ms:.0f}ms (순차라면 {len(texts)}배)")

    kept = sorted((j for j in judged if j["relevant"] >= RELEVANCE_FLOOR),
                  key=lambda j: -j["relevant"])[:KEEP]
    print(f"\n재랭킹 상위 {len(kept)}건:")
    for j in kept:
        print(f"  {j['relevant']:.2f}  {j['doc'][:50]}")

    best = max((j["answerable"] for j in kept), default=0.0)
    if best < 1.0:
        print("\n남은 문서로 답할 수 없습니다. 재검색하거나 모른다고 답해야 합니다.")
    else:
        print(f"\n답변 가능 (answerable {best:.2f}). LLM에 넘길 수 있습니다.")


if __name__ == "__main__":
    asyncio.run(run())
