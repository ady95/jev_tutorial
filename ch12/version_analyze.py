# -*- coding: utf-8 -*-
"""12-7 의 표를 원자료에서 다시 낸다 (API 호출 없음).

    python ch12/version_analyze.py                          책의 원자료로
    python ch12/version_analyze.py version_compare_result.json   직접 잰 결과로

9부와의 짝지은 비교·오프라인 하이브리드는 9부 원자료(ch09/results/book/)의 LLM 답을 씁니다.
LLM 을 다시 부르지 않으므로, 같은 문항에 대한 '고정된 과거 답'과의 비교입니다.
"""
import json
import math
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "ch12", "results", "book", "v114_2026-10-19.json")
OLD = os.path.join(ROOT, "ch09", "results", "book", "benchmark_2026-09-23.json")
LABELS = ["billing", "technical", "sales", "other"]
GRID = (0.5, 0.7, 0.8, 0.9, 0.95)

d = json.load(open(RAW, encoding="utf-8"))
old = json.load(open(OLD, encoding="utf-8"))
M = d["models"]
RUNS = sorted({int(k.split("|")[3]) for k in d["dept"]})


def acc(rows):
    return sum(r["pred"] == r["truth"] for r in rows) / len(rows)


def brier(rows):
    return statistics.mean(sum((r["probs"].get(l, 0) - (l == r["truth"])) ** 2 for l in LABELS) for r in rows)


def ece(rows):
    n, tot = len(rows), 0.0
    for i in range(10):
        lo, hi = i / 10, (i + 1) / 10
        b = [r for r in rows if (lo < r["conf"] <= hi) or (i == 0 and r["conf"] == 0)]
        if b:
            tot += len(b) / n * abs(statistics.mean(r["conf"] for r in b)
                                    - statistics.mean(r["pred"] == r["truth"] for r in b))
    return tot


def pick(rows):
    """개발셋에서만 — 게이트 구간이 무오류인 가장 낮은 임계값. 없으면 None."""
    for th in GRID:
        g = [r for r in rows if r["conf"] >= th]
        if g and all(r["pred"] == r["truth"] for r in g):
            return th
    return None


def gate(rows, th):
    g = [r for r in rows if th is not None and r["conf"] >= th]
    return len(g), (sum(r["pred"] == r["truth"] for r in g) / len(g) if g else None)


def sign_p(a, b):
    n, k = a + b, min(a, b)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0


def rows(m, var, split, run):
    return d["dept"][f"{m}|{var}|{split}|{run}"]


print("원자료:", os.path.basename(RAW), "  회차:", RUNS)
print("응답 모델:", {m: sorted({r["model"] for k, v in d["dept"].items() if k.startswith(m) for r in v}) for m in M})

for var, title in (("plain", "instructions 없음 (4부·9부 조건)"), ("instr", "instructions 있음 (12-4 조건)")):
    print(f"\n[부서 분류 — {title}]")
    for m in M:
        th = pick(rows(m, var, "dev", RUNS[0]))
        for split in ("dev", "holdout"):
            rs = [rows(m, var, split, r) for r in RUNS]
            a = [acc(x) for x in rs]
            gs = [gate(x, th) for x in rs]
            print(f"  {m} {split:7} 정확도 {statistics.mean(a):.3f} ({min(a):.3f}~{max(a):.3f})  "
                  f"Brier {statistics.mean(brier(x) for x in rs):.4f}  ECE {statistics.mean(ece(x) for x in rs):.4f}  "
                  f"임계값 {th}  게이트 {[g[0] for g in gs]}건 신뢰도 "
                  f"{[None if g[1] is None else round(g[1], 3) for g in gs]}")

print("\n[confidence 공식 (4·p_max − 1) / 3 과의 차이 — 모델마다 두 조건 전부]")
for m in M:
    diffs = [abs(r["conf"] - (4 * max(r["probs"].values()) - 1) / 3)
             for k, v in d["dept"].items() if k.startswith(m) for r in v]
    print(f"  {m} 최대 {max(diffs):.4f}  (n={len(diffs)})")

print("\n[같은 문항, 두 버전 (instructions 없음, 1회차)]")
for split in ("dev", "holdout"):
    x0, x1 = rows(M[0], "plain", split, RUNS[0]), rows(M[1], "plain", split, RUNS[0])
    up = sum(a["pred"] != a["truth"] and b["pred"] == b["truth"] for a, b in zip(x0, x1))
    dn = sum(a["pred"] == a["truth"] and b["pred"] != b["truth"] for a, b in zip(x0, x1))
    print(f"  {split:7} {M[1]}만 맞힘 {up}  {M[0]}만 맞힘 {dn}  (부호 검정 p={sign_p(up, dn):.2f})")

print("\n[9부 LLM 답과 짝지은 비교 · 오프라인 하이브리드 (LLM 답은 2026-09-23 원자료)]")
for m in M:
    th = pick(rows(m, "plain", "dev", RUNS[0]))
    for split, olds in (("dev", [old["dev"]]), ("holdout", old["holdout"])):
        for i, o in zip(RUNS, olds):
            jr, it = rows(m, "plain", split, i), o["items"]
            if [x["truth"] for x in it][:len(jr)] != [r["truth"] for r in jr]:
                print("  문항 순서가 9부 원자료와 다릅니다 — 건너뜀")
                continue
            it = it[:len(jr)]
            a = sum(r["pred"] == r["truth"] and x["frontier"] != x["truth"] for r, x in zip(jr, it))
            b = sum(r["pred"] != r["truth"] and x["frontier"] == x["truth"] for r, x in zip(jr, it))
            hyb = [r["pred"] if (th is not None and r["conf"] >= th) else x["frontier"] for r, x in zip(jr, it)]
            hacc = sum(h == x["truth"] for h, x in zip(hyb, it)) / len(it)
            extra = f"  38번 {jr[38]['pred']}({jr[38]['conf']:.2f})" if split == "holdout" and len(jr) > 38 else ""
            print(f"  {m} {split} {i}회  Jev {acc(jr):.3f}  Jev만/프런티어만 {a}/{b}  하이브리드 {hacc:.3f}{extra}")

print("\n[5부 환불 판정 (임계값 0.5)]")
for m in M:
    print(f"  {m}", [round(sum((x["p"] >= 0.5) == x["truth"] for x in d["refund"][f"{m}|{r}"])
                           / len(d["refund"][f"{m}|{r}"]), 3) for r in RUNS])

print("\n[지연 — 질문 수별 중앙값 5회]")
for m in M:
    print(f"  {m}", {k.split("|")[1]: f"{statistics.median(v['ms']):.0f}ms"
                     for k, v in d["latency"].items() if k.startswith(m)})
    ms = sorted(r["ms"] for k, v in d["dept"].items() if k.startswith(m + "|plain") for r in v)
    print(f"    분류 호출 P50 {ms[len(ms) // 2]:.0f}ms (n={len(ms)})")
