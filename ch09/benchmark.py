# -*- coding: utf-8 -*-
"""09-1 실습: 규칙 / 소형 LLM / 프런티어 LLM / Jev 4파전 벤치마크.

같은 평가셋, 같은 부서 정의, 같은 회선, 각 방식 워밍업 1회 후 측정합니다.

주의: LLM 호출이 많습니다. 실행 전 단가를 확인하세요.
"""
import io
import json
import os
import re
import statistics
import sys
import time

sys.path.insert(0, ".")
from _common import (LLM_FRONTIER, LLM_SMALL, pct, require_jev, require_llm, warmup_jev)
from dataset.inquiries import DEPARTMENTS, LABELS, TEXTS, TRUTHS

require_jev()
require_llm()
from openai import OpenAI
from typesafe_sdk import Choice, TypeSafeClient

oa = OpenAI()
DEPT = Choice(criteria=DEPARTMENTS)

PROMPT = ("다음 고객 문의를 담당 부서로 분류하세요.\n\n"
          + "\n".join(f"- {k}: {v}" for k, v in DEPARTMENTS.items())
          + "\n\n문의: {q}\n\n부서 이름 하나만 답하세요. 다른 말은 쓰지 마세요.")

# 비교군으로 쓸 규칙은 성의껏 만들어야 공정합니다.
RULES = [
    ("billing", ["환불", "결제", "청구", "요금", "세금계산서", "영수증",
                 "카드", "부가세", "입금", "정산"]),
    ("technical", ["오류", "에러", "안 됩니다", "안됩니다", "멈춰", "실패", "버그",
                   "로그인", "api", "깨져", "느립니다"]),
    ("sales", ["견적", "플랜", "도입", "할인", "체험", "제휴", "파트너", "상담", "계약"]),
]


def rule_predict(text):
    low = text.lower()
    best, hits = "other", 0
    for label, keywords in RULES:
        c = sum(1 for k in keywords if k in low)
        if c > hits:
            best, hits = label, c
    return best


def llm_run(model, texts):
    """형식 오류는 따로 세되 정확도에서는 정규식으로 구제합니다."""
    oa.chat.completions.create(model=model,
                               messages=[{"role": "user", "content": PROMPT.format(q="워밍업")}])
    lat, out, preds, fmt_err = [], 0, [], 0
    for t in texts:
        t0 = time.perf_counter()
        r = oa.chat.completions.create(model=model,
                                       messages=[{"role": "user", "content": PROMPT.format(q=t)}])
        lat.append((time.perf_counter() - t0) * 1000)
        out += r.usage.completion_tokens
        txt = (r.choices[0].message.content or "").strip().lower()
        m = re.fullmatch(r"(billing|technical|sales|other)\.?", txt)
        if m:
            preds.append(m.group(1))
        else:
            fmt_err += 1
            m2 = re.search(r"billing|technical|sales|other", txt)
            preds.append(m2.group(0) if m2 else "other")
    return preds, lat, out, fmt_err


def jev_run(texts):
    lat, out, preds, probs, confs = [], 0, [], [], []
    with TypeSafeClient() as c:
        warmup_jev(c, DEPT)
        for t in texts:
            t0 = time.perf_counter()
            r = c.system_one(state=t, questions={"d": DEPT})
            lat.append((time.perf_counter() - t0) * 1000)
            out += r.usage.output_tokens
            a = r.choices["d"]
            preds.append(a.choice)
            probs.append(dict(a.probabilities))
            confs.append(a.confidence)
    return preds, lat, out, probs, confs


def main():
    n = len(TEXTS)
    rows = []

    print("[1/4] 규칙 엔진")
    t0 = time.perf_counter()
    rule_preds = [rule_predict(t) for t in TEXTS]
    rule_ms = (time.perf_counter() - t0) * 1000 / n
    rows.append({"name": "규칙 엔진",
                 "acc": sum(p == t for p, t in zip(rule_preds, TRUTHS)) / n,
                 "mean": rule_ms, "p50": rule_ms, "p95": rule_ms, "p99": rule_ms,
                 "out_tok": 0.0, "fmt_err": 0, "has_prob": False})

    for i, model in enumerate([LLM_SMALL, LLM_FRONTIER], start=2):
        print(f"[{i}/4] LLM ({model})")
        p, lat, out, fe = llm_run(model, TEXTS)
        rows.append({"name": f"LLM ({model})",
                     "acc": sum(a == b for a, b in zip(p, TRUTHS)) / n,
                     "mean": statistics.mean(lat), "p50": pct(lat, 50),
                     "p95": pct(lat, 95), "p99": pct(lat, 99),
                     "out_tok": out / n, "fmt_err": fe, "has_prob": False})

    print("[4/4] Jev")
    jp, jlat, jout, jprobs, jconfs = jev_run(TEXTS)
    correct = [a == b for a, b in zip(jp, TRUTHS)]
    brier = sum(sum((pr.get(l, 0.0) - (1.0 if l == tr else 0.0)) ** 2 for l in LABELS)
                for pr, tr in zip(jprobs, TRUTHS)) / n
    e = 0.0
    for i in range(10):
        lo, hi = i / 10, (i + 1) / 10
        idx = [k for k, c in enumerate(jconfs) if lo < c <= hi]
        if idx:
            mc = sum(jconfs[k] for k in idx) / len(idx)
            ma = sum(correct[k] for k in idx) / len(idx)
            e += len(idx) / n * abs(mc - ma)
    rows.append({"name": "Jev", "acc": sum(correct) / n,
                 "mean": statistics.mean(jlat), "p50": pct(jlat, 50),
                 "p95": pct(jlat, 95), "p99": pct(jlat, 99),
                 "out_tok": jout / n, "fmt_err": 0, "has_prob": True,
                 "brier": brier, "ece": e})

    print(f"\n{'방식':26} {'정확도':>7} {'평균ms':>8} {'P50':>7} {'P95':>7} "
          f"{'P99':>8} {'출력tok':>8} {'형식오류':>8} {'확률':>5}")
    for r in rows:
        print(f"{r['name']:26} {r['acc']:7.3f} {r['mean']:8.0f} {r['p50']:7.0f} "
              f"{r['p95']:7.0f} {r['p99']:8.0f} {r['out_tok']:8.1f} "
              f"{r['fmt_err']:8d} {'있음' if r['has_prob'] else '없음':>5}")
    print(f"\nJev 보정: Brier {brier:.4f}  ECE {e:.4f}")
    print("\n평균만 보지 마세요. P95와 P99가 이야기를 바꿉니다.")
    print("다음: python ch09/hybrid_bench.py 로 하이브리드를 비교군에 추가하세요.")

    os.makedirs("out", exist_ok=True)
    json.dump({"n": n, "rows": rows},
              io.open("out/benchmark.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("저장 -> out/benchmark.json")


if __name__ == "__main__":
    main()
