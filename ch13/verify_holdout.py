# -*- coding: utf-8 -*-
"""verify_cost2.py 와 완전히 같은 절차를 홀드아웃 30건에 적용한다.

verify_cost2 는 (dev + holdout)[:30] 을 썼는데 dev 가 정확히 30건이라
실제로는 개발셋만 쟀다. 여기서는 손대지 않은 홀드아웃 30건으로 다시 잰다.
임계값 0.5, 질문 5개, 프롬프트는 그대로 두고 데이터만 바꾼다.
"""
import json, os, random, statistics, sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from dotenv import load_dotenv
load_dotenv(HERE.parent / ".env")
os.environ.setdefault("OPENAI_API_BASE", os.environ.get("OPENAI_BASE_URL", ""))

from verify_cost import (ONE, PROMPT_FIVE, PROMPT_ONE, QUESTIONS, as_text,
                         BY_ID, jev_call, llm_call)

RNG = random.Random(11)   # verify_cost2 와 같은 씨앗


def main():
    rows = json.loads((HERE / "result_naive.json").read_text(encoding="utf-8"))
    sample = rows["holdout"]                      # <- 여기만 다르다

    jev_call({"질문": "워밍업", "답변": "워밍업"}, ONE)
    jev_call({"질문": "워밍업", "답변": "워밍업"}, QUESTIONS)
    llm_call(PROMPT_ONE.format(docs="-", q="워밍업", a="워밍업"))
    llm_call(PROMPT_FIVE.format(docs="-", q="워밍업", a="워밍업"))

    acc = {k: ([], [], []) for k in ("jev1", "llm1", "jev5", "llm5")}
    disagree, allrows = [], []

    for r in sample:
        docs = "\n\n".join(as_text(BY_ID[i]) for i in r["docs"]) or "(검색된 문서 없음)"
        state = {"질문": r["q"], "검색된 문서": docs, "답변": r["answer"]}
        v = {}

        def do_jev1():
            ms, ti, to, resp = jev_call(state, ONE)
            v["jev"] = resp.nouls["grounded"].noul
            return "jev1", ms, ti, to

        def do_llm1():
            ms, ti, to, text = llm_call(PROMPT_ONE.format(docs=docs, q=r["q"], a=r["answer"]))
            v["llm"] = text.lower().startswith("yes")
            return "llm1", ms, ti, to

        def do_jev5():
            return ("jev5",) + jev_call(state, QUESTIONS)[:3]

        def do_llm5():
            return ("llm5",) + llm_call(PROMPT_FIVE.format(docs=docs, q=r["q"], a=r["answer"]))[:3]

        tasks = [do_jev1, do_llm1, do_jev5, do_llm5]
        RNG.shuffle(tasks)
        for t in tasks:
            key, ms, ti, to = t()
            for L, x in zip(acc[key], (ms, ti, to)):
                L.append(x)

        jev_yes = v["jev"] >= 0.5
        rec = {"q": r["q"], "group": r["group"], "grade": r["grade"],
               "p_jev": v["jev"], "jev": jev_yes, "llm": v["llm"],
               "docs": r["docs"], "answer": r["answer"][:130]}
        allrows.append(rec)
        if jev_yes != v["llm"]:
            disagree.append(rec)

    def show(name, key):
        lat, ti, to = acc[key]
        print(f"  {name:26} P50 {statistics.median(lat):7.0f} ms   "
              f"평균 {statistics.mean(lat):7.0f} ms   "
              f"입력 {statistics.mean(ti):6.0f} tok   출력 {statistics.mean(to):5.1f} tok")

    print(f"\n홀드아웃 독립 평가  (n={len(sample)})")
    print("\n판단 1개"); show("Jev", "jev1"); show("LLM", "llm1")
    print("\n판단 5개"); show("Jev  (한 번의 호출)", "jev5"); show("LLM  (한 프롬프트에 묶음)", "llm5")
    j1, l1 = (statistics.median(acc[k][0]) for k in ("jev1", "llm1"))
    j5, l5 = (statistics.median(acc[k][0]) for k in ("jev5", "llm5"))
    print(f"\n  지연 비율   판단 1개 {l1/j1:.1f}배   판단 5개 {l5/j5:.1f}배")
    print(f"  1개 -> 5개  Jev {j5/j1:.2f}배   LLM {l5/l1:.2f}배")

    # 정답 기준을 둘로 나눠 본다: 군(群) 기준과 채점 등급 기준
    def truth_by_group(r):   return r["group"] != "B"
    def truth_by_grade(r):
        if r["group"] == "B": return False
        return r["grade"] == "정답"

    for name, fn in (("군 기준", truth_by_group), ("채점등급 기준", truth_by_grade)):
        jev_ok = sum(1 for r in allrows if r["jev"] == fn(r))
        llm_ok = sum(1 for r in allrows if r["llm"] == fn(r))
        print(f"\n  {name}   Jev {jev_ok}/{len(allrows)}   LLM {llm_ok}/{len(allrows)}")

    print(f"\n판정이 어긋난 건  {len(disagree)}/{len(sample)}")
    for d in disagree:
        who_g = "Jev" if d["jev"] == truth_by_group(d) else "LLM"
        who_r = "Jev" if d["jev"] == truth_by_grade(d) else "LLM"
        print(f"\n  [{d['group']}군 / {d['grade']}]  군기준 {who_g} 맞음 · 등급기준 {who_r} 맞음")
        print(f"    Jev {d['p_jev']:.2f}({'있음' if d['jev'] else '없음'})  "
              f"LLM {'있음' if d['llm'] else '없음'}   검색 {d['docs']}")
        print(f"    Q {d['q']}")
        print(f"    A {' '.join(d['answer'].split())[:110]}")

    (HERE / "verify_holdout.json").write_text(json.dumps(
        {"latency": {k: {"ms": v[0], "in": v[1], "out": v[2]} for k, v in acc.items()},
         "rows": allrows, "disagree": disagree}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
