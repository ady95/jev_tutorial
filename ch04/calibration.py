# -*- coding: utf-8 -*-
"""04-2, 04-3 실습: 정확도, 보정(Brier/ECE), Risk-Coverage 측정.

평가셋 60건을 Jev로 분류하고 결과를 out/calibration.json 에 저장합니다.
차트는 ch04/charts.py 로 그립니다.
"""
import io
import json
import os
import sys
import time

sys.path.insert(0, ".")
from _common import require_jev, warmup_jev
from dataset.inquiries import AMBIGUOUS, DEPARTMENTS, LABELS, TEXTS, TRUTHS

require_jev()
from typesafe_sdk import Choice, TypeSafeClient

DEPT = Choice(criteria=DEPARTMENTS)
BINS = 10


def brier_score(rows):
    total = 0.0
    for r in rows:
        total += sum((r["probs"].get(l, 0.0) - (1.0 if l == r["truth"] else 0.0)) ** 2
                     for l in LABELS)
    return total / len(rows)


def ece(rows, n_bins=BINS):
    n = len(rows)
    total, buckets = 0.0, []
    for i in range(n_bins):
        lo, hi = i / n_bins, (i + 1) / n_bins
        b = [r for r in rows if lo < r["conf"] <= hi]
        if not b:
            buckets.append({"lo": lo, "hi": hi, "n": 0, "conf": None, "acc": None})
            continue
        mc = sum(r["conf"] for r in b) / len(b)
        ma = sum(r["correct"] for r in b) / len(b)
        total += len(b) / n * abs(mc - ma)
        buckets.append({"lo": lo, "hi": hi, "n": len(b), "conf": mc, "acc": ma})
    return total, buckets


def risk_coverage(rows, thresholds=(0.0, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99)):
    n = len(rows)
    out = []
    for th in thresholds:
        kept = [r for r in rows if r["conf"] >= th]
        risk = (1 - sum(r["correct"] for r in kept) / len(kept)) if kept else 0.0
        out.append({"threshold": th, "coverage": len(kept) / n,
                    "risk": risk, "n_auto": len(kept)})
    return out


def main():
    rows = []
    with TypeSafeClient() as client:
        warmup_jev(client, DEPT)
        for text, truth, amb in zip(TEXTS, TRUTHS, AMBIGUOUS):
            t0 = time.perf_counter()
            a = client.system_one(state=text, questions={"d": DEPT}).choices["d"]
            rows.append({"text": text, "truth": truth, "ambiguous": amb,
                         "pred": a.choice, "conf": a.confidence,
                         "probs": dict(a.probabilities),
                         "ms": (time.perf_counter() - t0) * 1000,
                         "correct": a.choice == truth})

    n = len(rows)
    clear = [r for r in rows if not r["ambiguous"]]
    amb = [r for r in rows if r["ambiguous"]]
    print(f"전체 정확도  {sum(r['correct'] for r in rows)/n:.3f}  "
          f"({sum(r['correct'] for r in rows)}/{n})")
    print(f"명확한 건    {sum(r['correct'] for r in clear)/len(clear):.3f}")
    print(f"애매한 건    {sum(r['correct'] for r in amb)/len(amb):.3f}")

    b = brier_score(rows)
    e, buckets = ece(rows)
    print(f"\nBrier Score  {b:.4f}   ECE {e:.4f}")

    print(f"\n{'구간':>12} {'건수':>5} {'평균conf':>9} {'정확도':>8} {'차이':>8}")
    for x in buckets:
        if x["n"]:
            print(f"  {x['lo']:.1f}~{x['hi']:.1f}   {x['n']:5d} "
                  f"{x['conf']:9.3f} {x['acc']:8.3f} {x['acc']-x['conf']:+8.3f}")
    print("  (건수가 적은 구간의 출렁임은 잡음입니다. 점 크기를 보세요)")

    rc = risk_coverage(rows)
    print(f"\n{'임계값':>7} {'자동화율':>9} {'오류율':>8} {'자동':>6} {'검토':>6}")
    for r in rc:
        print(f"  {r['threshold']:5.2f} {r['coverage']:9.1%} {r['risk']:8.1%} "
              f"{r['n_auto']:6d} {n - r['n_auto']:6d}")

    print("\n틀린 건 (confidence 낮은 순):")
    for r in sorted((r for r in rows if not r["correct"]), key=lambda r: r["conf"]):
        tag = "[애매]" if r["ambiguous"] else "      "
        print(f"  conf={r['conf']:.2f} 정답={r['truth']:10} 예측={r['pred']:10} "
              f"{tag} {r['text'][:34]}")

    os.makedirs("out", exist_ok=True)
    json.dump({"n": n, "accuracy": sum(r["correct"] for r in rows) / n,
               "brier": b, "ece": e, "bins": buckets,
               "risk_coverage": rc, "rows": rows},
              io.open("out/calibration.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("\n저장 -> out/calibration.json  (차트는 python ch04/charts.py)")


if __name__ == "__main__":
    main()
