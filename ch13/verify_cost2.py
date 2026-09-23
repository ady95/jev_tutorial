# -*- coding: utf-8 -*-
"""verify_cost.py 재측정 — 호출 순서 편향 제거 + 불일치 건 조사.

1차 측정에서 Jev 판단 1개가 5개보다 느리게 나왔다. 1개 호출이 항상 먼저
나가 연결 비용을 더 물었기 때문으로 보인다. 네 가지 호출의 순서를 건마다
섞어 다시 잰다.

그리고 두 방식의 판정이 어긋난 건을 들여다본다. 어느 쪽이 틀렸는지에 따라
서술이 완전히 달라진다.
"""
import json
import os
import random
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from dotenv import load_dotenv

load_dotenv(HERE.parent / ".env")
os.environ.setdefault("OPENAI_API_BASE", os.environ.get("OPENAI_BASE_URL", ""))

from verify_cost import (ONE, PROMPT_FIVE, PROMPT_ONE, QUESTIONS, as_text,
                         BY_ID, jev_call, llm_call)

RNG = random.Random(11)


def main():
    rows = json.loads((HERE / "result_naive.json").read_text(encoding="utf-8"))
    sample = (rows["dev"] + rows["holdout"])[:30]

    # 네 종류 모두 워밍업해 첫 호출 비용을 뺀다
    jev_call({"질문": "워밍업", "답변": "워밍업"}, ONE)
    jev_call({"질문": "워밍업", "답변": "워밍업"}, QUESTIONS)
    llm_call(PROMPT_ONE.format(docs="-", q="워밍업", a="워밍업"))
    llm_call(PROMPT_FIVE.format(docs="-", q="워밍업", a="워밍업"))

    acc = {k: ([], [], []) for k in ("jev1", "llm1", "jev5", "llm5")}
    disagree = []

    for r in sample:
        docs = "\n\n".join(as_text(BY_ID[i]) for i in r["docs"]) or "(검색된 문서 없음)"
        state = {"질문": r["q"], "검색된 문서": docs, "답변": r["answer"]}
        verdicts = {}

        def do_jev1():
            ms, ti, to, resp = jev_call(state, ONE)
            verdicts["jev"] = resp.nouls["grounded"].noul
            return "jev1", ms, ti, to

        def do_llm1():
            ms, ti, to, text = llm_call(
                PROMPT_ONE.format(docs=docs, q=r["q"], a=r["answer"]))
            verdicts["llm"] = text.lower().startswith("yes")
            return "llm1", ms, ti, to

        def do_jev5():
            return ("jev5",) + jev_call(state, QUESTIONS)[:3]

        def do_llm5():
            return ("llm5",) + llm_call(
                PROMPT_FIVE.format(docs=docs, q=r["q"], a=r["answer"]))[:3]

        tasks = [do_jev1, do_llm1, do_jev5, do_llm5]
        RNG.shuffle(tasks)                      # 순서 편향 제거
        for t in tasks:
            key, ms, ti, to = t()
            for L, v in zip(acc[key], (ms, ti, to)):
                L.append(v)

        jev_yes = verdicts["jev"] >= 0.5
        if jev_yes != verdicts["llm"]:
            disagree.append({
                "q": r["q"], "group": r["group"], "grade": r["grade"],
                "p_jev": verdicts["jev"], "jev": jev_yes, "llm": verdicts["llm"],
                "docs": r["docs"], "answer": r["answer"][:130],
            })

    def show(name, key):
        lat, ti, to = acc[key]
        print(f"  {name:26} P50 {statistics.median(lat):7.0f} ms   "
              f"평균 {statistics.mean(lat):7.0f} ms   "
              f"입력 {statistics.mean(ti):6.0f} tok   출력 {statistics.mean(to):5.1f} tok")

    print(f"\n순서를 섞어 다시 측정  (n={len(sample)})")
    print("\n판단 1개")
    show("Jev", "jev1")
    show("LLM", "llm1")
    print("\n판단 5개")
    show("Jev  (한 번의 호출)", "jev5")
    show("LLM  (한 프롬프트에 묶음)", "llm5")

    j1, l1 = (statistics.median(acc[k][0]) for k in ("jev1", "llm1"))
    j5, l5 = (statistics.median(acc[k][0]) for k in ("jev5", "llm5"))
    print(f"\n  지연 비율   판단 1개 {l1/j1:.1f}배   판단 5개 {l5/j5:.1f}배")
    print(f"  1개 -> 5개  Jev {j5/j1:.2f}배   LLM {l5/l1:.2f}배")

    print(f"\n판정이 어긋난 건  {len(disagree)}/{len(sample)}")
    for d in disagree:
        truth = "근거 없음이 정답" if d["group"] == "B" else "근거 있음이 정답"
        who = ("Jev 맞음" if (d["jev"] is (d["group"] != "B")) else "LLM 맞음")
        print(f"\n  [{d['group']}군 / {d['grade']}]  {truth} -> {who}")
        print(f"    Jev {d['p_jev']:.2f}({'근거있음' if d['jev'] else '근거없음'})  "
              f"LLM {'근거있음' if d['llm'] else '근거없음'}   검색 {d['docs']}")
        print(f"    Q {d['q']}")
        print(f"    A {' '.join(d['answer'].split())[:110]}")

    (HERE / "verify_cost2.json").write_text(json.dumps(
        {"latency": {k: {"ms": v[0], "in": v[1], "out": v[2]} for k, v in acc.items()},
         "disagree": disagree}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
