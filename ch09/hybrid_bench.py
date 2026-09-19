# -*- coding: utf-8 -*-
"""09-4 실습: 하이브리드(Jev 게이트 + 프런티어 LLM)를 비교군에 추가한다.

9부의 결론이 여기서 나옵니다. 6번까지만 재고 끝내면 결론이 달라집니다.
"""
import io
import json
import os
import re
import statistics
import sys
import time

sys.path.insert(0, ".")
from _common import LLM_FRONTIER, pct, require_jev, require_llm, warmup_jev
from dataset.inquiries import DEPARTMENTS, TEXTS, TRUTHS

require_jev()
require_llm()
from openai import OpenAI
from typesafe_sdk import Choice, TypeSafeClient

oa = OpenAI()
DEPT = Choice(criteria=DEPARTMENTS)
THRESHOLD = 0.90

BASE = ("다음 고객 문의를 담당 부서로 분류하세요.\n\n"
        + "\n".join(f"- {k}: {v}" for k, v in DEPARTMENTS.items())
        + "\n\n문의: {q}\n\n부서 이름 하나만 답하세요.")


def ask(text, hint=None, alts=None):
    p = BASE.format(q=text)
    if hint:
        p += (f"\n\n참고: 1차 분류기는 '{hint}'로 봤으나 확신이 낮습니다"
              f"(후보별 확률 {alts}). 다시 판단해주세요.")
    t0 = time.perf_counter()
    r = oa.chat.completions.create(model=LLM_FRONTIER,
                                   messages=[{"role": "user", "content": p}])
    ms = (time.perf_counter() - t0) * 1000
    m = re.search(r"billing|technical|sales|other",
                  (r.choices[0].message.content or "").lower())
    return (m.group(0) if m else "other"), ms, r.usage.completion_tokens


def main():
    n = len(TEXTS)

    jev = []
    with TypeSafeClient() as c:
        warmup_jev(c, DEPT)
        for t in TEXTS:
            t0 = time.perf_counter()
            a = c.system_one(state=t, questions={"d": DEPT}).choices["d"]
            jev.append({"pred": a.choice, "conf": a.confidence,
                        "ms": (time.perf_counter() - t0) * 1000,
                        "probs": {k: round(v, 3) for k, v in
                                  sorted(a.probabilities.items(), key=lambda kv: -kv[1])[:3]}})

    hyb_pred, hyb_ms, calls, tok = [], [], 0, 0
    for j, text in zip(jev, TEXTS):
        if j["conf"] >= THRESHOLD:
            hyb_pred.append(j["pred"])
            hyb_ms.append(j["ms"])
        else:
            p, ms, t = ask(text, hint=j["pred"], alts=j["probs"])
            hyb_pred.append(p)
            hyb_ms.append(j["ms"] + ms)
            calls += 1
            tok += t

    gate = [j for j in jev if j["conf"] >= THRESHOLD]
    gate_acc = (sum(1 for j, t in zip(jev, TRUTHS)
                    if j["conf"] >= THRESHOLD and j["pred"] == t) / len(gate)) if gate else 0.0
    acc = sum(a == b for a, b in zip(hyb_pred, TRUTHS)) / n

    print(f"게이트 통과(conf >= {THRESHOLD})  {len(gate)}/{n} = {len(gate)/n:.1%}")
    print(f"그 구간 정확도                    {gate_acc:.3f}")
    print(f"LLM 재검토                        {calls}건 ({calls/n:.1%}), 출력 {tok} tok")
    print(f"\n하이브리드 정확도   {acc:.3f}")
    print(f"하이브리드 지연     평균 {statistics.mean(hyb_ms):.0f}ms  "
          f"P50 {pct(hyb_ms, 50):.0f}  P95 {pct(hyb_ms, 95):.0f}  P99 {pct(hyb_ms, 99):.0f}")

    src = "out/benchmark.json"
    if os.path.exists(src):
        rows = json.load(io.open(src, encoding="utf-8"))["rows"]
        print(f"\n{'방식':26} {'정확도':>8} {'P50':>8}")
        for r in rows:
            print(f"{r['name']:26} {r['acc']:8.3f} {r['p50']:7.0f}ms")
        print(f"{'하이브리드':26} {acc:8.3f} {pct(hyb_ms, 50):7.0f}ms")
    else:
        print("\n(ch09/benchmark.py 를 먼저 돌리면 전체 비교표가 나옵니다)")

    print("\n게이트 구간 정확도가 1.000에 가깝다면, 그 구간에 LLM을 부르는 것은 낭비입니다.")


if __name__ == "__main__":
    main()
