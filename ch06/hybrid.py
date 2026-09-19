# -*- coding: utf-8 -*-
"""06-1, 06-2 실습: Jev 게이트 + LLM 재검토 하이브리드.

세 전략(전량 LLM / 전량 Jev / 하이브리드)의 정확도와 비용을 비교합니다.
"""
import re
import statistics
import sys
import time

sys.path.insert(0, ".")
from _common import LLM_FRONTIER, require_jev, require_llm, warmup_jev
from dataset.inquiries import DEPARTMENTS, TEXTS, TRUTHS

require_jev()
require_llm()
from openai import OpenAI
from typesafe_sdk import Choice, TypeSafeClient

oa = OpenAI()
DEPT = Choice(criteria=DEPARTMENTS)
THRESHOLD = 0.90

BASE_PROMPT = ("다음 고객 문의를 담당 부서로 분류하세요.\n\n"
               + "\n".join(f"- {k}: {v}" for k, v in DEPARTMENTS.items())
               + "\n\n문의: {q}\n\n부서 이름 하나만 답하세요.")


def ask_llm(text, hint=None, alts=None):
    p = BASE_PROMPT.format(q=text)
    if hint:
        p += (f"\n\n참고: 1차 분류기는 '{hint}'로 판단했으나 확신이 낮습니다. "
              f"후보별 확률은 {alts} 입니다. 다시 판단해주세요.")
    t0 = time.perf_counter()
    r = oa.chat.completions.create(model=LLM_FRONTIER,
                                   messages=[{"role": "user", "content": p}])
    ms = (time.perf_counter() - t0) * 1000
    m = re.search(r"billing|technical|sales|other",
                  (r.choices[0].message.content or "").lower())
    return (m.group(0) if m else "other"), ms, r.usage.completion_tokens


def main():
    n = len(TEXTS)

    print("[1] Jev 단독")
    jev = []
    with TypeSafeClient() as client:
        warmup_jev(client, DEPT)
        for text in TEXTS:
            t0 = time.perf_counter()
            a = client.system_one(state=text, questions={"d": DEPT}).choices["d"]
            jev.append({"pred": a.choice, "conf": a.confidence,
                        "ms": (time.perf_counter() - t0) * 1000,
                        "probs": {k: round(v, 3) for k, v in
                                  sorted(a.probabilities.items(), key=lambda kv: -kv[1])[:3]}})
    jev_acc = sum(j["pred"] == t for j, t in zip(jev, TRUTHS)) / n
    print(f"  정확도 {jev_acc:.3f}  평균 {statistics.mean(j['ms'] for j in jev):.0f}ms")

    print("\n[2] 전량 LLM")
    llm_pred, llm_ms = [], []
    for text in TEXTS:
        p, ms, _ = ask_llm(text)
        llm_pred.append(p)
        llm_ms.append(ms)
    llm_acc = sum(a == b for a, b in zip(llm_pred, TRUTHS)) / n
    print(f"  정확도 {llm_acc:.3f}  평균 {statistics.mean(llm_ms):.0f}ms")

    print(f"\n[3] 하이브리드 (conf < {THRESHOLD} 만 LLM 재검토)")
    hyb_pred, hyb_ms, calls = [], [], 0
    for j, text in zip(jev, TEXTS):
        if j["conf"] >= THRESHOLD:
            hyb_pred.append(j["pred"])
            hyb_ms.append(j["ms"])
        else:
            p, ms, _ = ask_llm(text, hint=j["pred"], alts=j["probs"])
            hyb_pred.append(p)
            hyb_ms.append(j["ms"] + ms)
            calls += 1
    hyb_acc = sum(a == b for a, b in zip(hyb_pred, TRUTHS)) / n

    gate = [j for j in jev if j["conf"] >= THRESHOLD]
    gate_acc = (sum(1 for j, t in zip(jev, TRUTHS)
                    if j["conf"] >= THRESHOLD and j["pred"] == t) / len(gate)) if gate else 0
    print(f"  게이트 통과 {len(gate)}/{n} = {len(gate)/n:.1%}, 그 구간 정확도 {gate_acc:.3f}")
    print(f"  LLM 재검토 {calls}건 ({calls/n:.1%})")
    print(f"  정확도 {hyb_acc:.3f}  평균 {statistics.mean(hyb_ms):.0f}ms")

    print(f"\n{'전략':16} {'정확도':>8} {'건당평균':>10} {'LLM 호출':>10}")
    print(f"{'전량 LLM':16} {llm_acc:8.3f} {statistics.mean(llm_ms):9.0f}ms {n:10d}")
    print(f"{'전량 Jev':16} {jev_acc:8.3f} "
          f"{statistics.mean(j['ms'] for j in jev):9.0f}ms {0:10d}")
    print(f"{'하이브리드':16} {hyb_acc:8.3f} {statistics.mean(hyb_ms):9.0f}ms {calls:10d}")
    print("\n책의 결과: 하이브리드가 전량 LLM과 정확도가 같으면서 LLM 호출은 38%.")


if __name__ == "__main__":
    main()
