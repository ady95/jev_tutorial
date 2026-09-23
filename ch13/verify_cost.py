# -*- coding: utf-8 -*-
"""같은 검증 일을 LLM으로 할 때와 Jev로 할 때.

지금까지 13부에서 잰 것은 전부 품질이었고 프롬프트가 이겼다. 여기서는
**품질이 같을 때의 비용과 지연**을 잰다. 9부의 결론이 이쪽이었다.

두 가지를 비교한다.

  1) 판단 하나          "답변이 문서에 근거하는가"
  2) 판단 다섯 개       근거·완결성·조건 명시·단정 수위·되물음 필요

두 번째가 핵심이다. Jev는 한 번의 호출로 다섯을 병렬 평가하고, LLM은
한 프롬프트에 묶으면 판단이 서로 간섭한다(1부 두 번째 절). 따로 부르면
비용이 다섯 배다.

이미 저장한 답변을 재사용하므로 에이전트는 다시 돌리지 않는다.
"""
import json
import os
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from dotenv import load_dotenv

load_dotenv(HERE.parent / ".env")
os.environ.setdefault("OPENAI_API_BASE", os.environ.get("OPENAI_BASE_URL", ""))

from langchain_typesafe import Noul, TypeSafeClassifier
from openai import OpenAI

from agent_tax import BY_ID
from corpus_tax import as_text

clf = TypeSafeClassifier()
oa = OpenAI()
LLM = os.getenv("TAX_AGENT_MODEL", "gpt-6-luna").replace("openai:", "")

QUESTIONS = {
    "grounded": Noul(
        instructions="답변에 담긴 사실이 검색된 문서에서 그대로 확인되는가?",
        criteria={"true": "답변의 수치와 조건이 문서에 적힌 것과 같다",
                  "false": "문서에 없는 수치나 조건을 말했거나 문서 내용을 뒤집었다"}),
    "complete": Noul(
        instructions="질문이 물은 것에 빠짐없이 답했는가?",
        criteria={"true": "질문의 모든 항목에 답했다", "false": "일부를 빠뜨렸다"}),
    "conditioned": Noul(
        instructions="답이 조건에 따라 갈리는 경우 그 조건을 밝혔는가?",
        criteria={"true": "적용 조건을 함께 적었거나 조건이 필요 없다",
                  "false": "조건을 밝히지 않고 하나로 단정했다"}),
    "not_overclaiming": Noul(
        instructions="문서가 말하지 않은 것까지 단정하지 않았는가?",
        criteria={"true": "문서 범위 안에서만 말했다", "false": "추론을 사실처럼 단정했다"}),
    "needs_followup": Noul(
        instructions="사용자에게 추가로 물어봐야 하는가?",
        criteria={"true": "조건이 빠져 답을 정할 수 없다", "false": "그대로 답할 수 있다"}),
}
ONE = {"grounded": QUESTIONS["grounded"]}

PROMPT_ONE = """다음 답변이 검색된 문서에 근거하는지 판정하세요.

[검색된 문서]
{docs}

[질문]
{q}

[답변]
{a}

문서의 수치·조건과 답변이 일치하면 yes, 문서에 없는 것을 말했거나 뒤집었으면 no.
yes 또는 no 한 단어로만 답하세요."""

PROMPT_FIVE = """다음 답변을 다섯 항목으로 판정하세요.

[검색된 문서]
{docs}

[질문]
{q}

[답변]
{a}

각 항목에 yes 또는 no 로만 답하고 JSON 한 줄로 출력하세요.
grounded: 답변의 사실이 문서에서 확인되는가
complete: 질문이 물은 것에 빠짐없이 답했는가
conditioned: 조건에 따라 갈리는 경우 조건을 밝혔는가
not_overclaiming: 문서가 말하지 않은 것을 단정하지 않았는가
needs_followup: 사용자에게 추가로 물어봐야 하는가"""


def llm_call(prompt):
    t0 = time.perf_counter()
    r = oa.chat.completions.create(model=LLM, messages=[{"role": "user", "content": prompt}])
    ms = (time.perf_counter() - t0) * 1000
    u = r.usage
    return ms, u.prompt_tokens, u.completion_tokens, r.choices[0].message.content.strip()


def jev_call(state, questions):
    t0 = time.perf_counter()
    r = clf.invoke({"state": state, "questions": questions})
    ms = (time.perf_counter() - t0) * 1000
    return ms, r.usage.input_tokens, r.usage.output_tokens, r


def summarize(name, lat, tin, tout):
    print(f"  {name:28} P50 {statistics.median(lat):7.0f} ms   "
          f"평균 {statistics.mean(lat):7.0f} ms   "
          f"입력 {statistics.mean(tin):6.0f} tok   출력 {statistics.mean(tout):5.1f} tok")


def main():
    rows = json.loads((HERE / "result_naive.json").read_text(encoding="utf-8"))
    sample = (rows["dev"] + rows["holdout"])[:30]

    # 워밍업
    jev_call({"질문": "워밍업", "답변": "워밍업"}, ONE)
    llm_call(PROMPT_ONE.format(docs="-", q="워밍업", a="워밍업"))

    acc = {k: ([], [], []) for k in ("jev1", "llm1", "jev5", "llm5")}
    agree = 0
    for r in sample:
        docs = "\n\n".join(as_text(BY_ID[i]) for i in r["docs"]) or "(검색된 문서 없음)"
        state = {"질문": r["q"], "검색된 문서": docs, "답변": r["answer"]}

        ms, ti, to, resp = jev_call(state, ONE)
        for L, v in zip(acc["jev1"], (ms, ti, to)):
            L.append(v)
        jev_yes = resp.nouls["grounded"].noul >= 0.5

        ms, ti, to, text = llm_call(PROMPT_ONE.format(docs=docs, q=r["q"], a=r["answer"]))
        for L, v in zip(acc["llm1"], (ms, ti, to)):
            L.append(v)
        llm_yes = text.lower().startswith("yes")
        agree += int(jev_yes == llm_yes)

        ms, ti, to, _ = jev_call(state, QUESTIONS)
        for L, v in zip(acc["jev5"], (ms, ti, to)):
            L.append(v)

        ms, ti, to, _ = llm_call(PROMPT_FIVE.format(docs=docs, q=r["q"], a=r["answer"]))
        for L, v in zip(acc["llm5"], (ms, ti, to)):
            L.append(v)

    print(f"\n판단 1개  (n={len(sample)})")
    summarize("Jev", *acc["jev1"])
    summarize("LLM", *acc["llm1"])
    print(f"\n판단 5개  (n={len(sample)})")
    summarize("Jev  (한 번의 호출)", *acc["jev5"])
    summarize("LLM  (한 프롬프트에 묶음)", *acc["llm5"])

    j1, l1 = statistics.median(acc["jev1"][0]), statistics.median(acc["llm1"][0])
    j5, l5 = statistics.median(acc["jev5"][0]), statistics.median(acc["llm5"][0])
    print(f"\n  지연 비율   판단 1개 {l1/j1:.1f}배   판단 5개 {l5/j5:.1f}배")
    print(f"  Jev 판단 1개 -> 5개 지연 증가  {j5/j1:.2f}배")
    print(f"  LLM 판단 1개 -> 5개 지연 증가  {l5/l1:.2f}배")
    print(f"  두 방식의 grounded 판정 일치   {agree}/{len(sample)} = {agree/len(sample):.1%}")

    (HERE / "verify_cost.json").write_text(
        json.dumps({k: {"ms": v[0], "in": v[1], "out": v[2]} for k, v in acc.items()},
                   ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
