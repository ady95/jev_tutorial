# -*- coding: utf-8 -*-
"""13-4 의 표를 측정 결과 파일에서 다시 뽑는다. 모델을 부르지 않는다.

    python ch13/aggregate13.py                      # 책에 실린 측정 결과로 집계
    python ch13/aggregate13.py cost_dev.json cost_holdout.json

인자를 주지 않으면 results/book/ 의 세 파일을 읽는다. 책 13-4 의 지연 비율 표,
판단 하나의 정확도 53/60, 경계 구간 표, 불일치 문항 겹침이 그대로 나와야 한다.

정답 기준은 채점 등급이다. B군(문서에 답이 없음)이면 "근거 없음"이 정답이고,
A·C군은 채점이 '정답'일 때만 "근거 있음"이 정답이다.
"""
import io
import json
import statistics
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).parent
BOOK = [HERE / "results" / "book" / n for n in
        ("cost_dev_run1.json", "cost_dev_run2.json", "cost_holdout.json")]


def truth(r):
    return r["group"] != "B" and r["grade"] == "정답"


def med(xs):
    return statistics.median(xs) if xs else float("nan")


def load(paths):
    runs = []
    for p in paths:
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        d.setdefault("meta", {})
        d["meta"].setdefault("name", Path(p).name)
        runs.append(d)
    return runs


def latency_tables(runs):
    print("=== 지연시간 (각 실행) ===")
    for d in runs:
        m, lat = d["meta"], d["latency"]
        print(f"\n[{m['name']}]  {m.get('split', '?')}  n={len(lat['jev1']['ms'])}")
        for key, name in (("jev1", "판단 1개  판단 모델"), ("llm1", "판단 1개  LLM"),
                          ("jev5", "판단 5개  판단 모델"), ("llm5", "판단 5개  LLM")):
            x = lat[key]
            reason = f"   추론 {statistics.mean(x['reason']):5.1f}" if x.get("reason") else ""
            print(f"  {name:18} P50 {med(x['ms']):6.0f} ms   평균 {statistics.mean(x['ms']):6.0f} ms"
                  f"   입력 {statistics.mean(x['in']):5.0f}   출력 {statistics.mean(x['out']):6.1f}{reason}")

    print("\n=== 지연 비율 ===")
    print(f"{'':24}" + "".join(f"{d['meta']['name'][:14]:>16}" for d in runs))
    rows = [("판단 1개 지연 비율", lambda L: med(L["llm1"]["ms"]) / med(L["jev1"]["ms"])),
            ("판단 5개 지연 비율", lambda L: med(L["llm5"]["ms"]) / med(L["jev5"]["ms"])),
            ("1개 -> 5개  판단 모델", lambda L: med(L["jev5"]["ms"]) / med(L["jev1"]["ms"])),
            ("1개 -> 5개  LLM", lambda L: med(L["llm5"]["ms"]) / med(L["llm1"]["ms"]))]
    for name, f in rows:
        print(f"{name:24}" + "".join(f"{f(d['latency']):14.2f}배" for d in runs))


def quality_tables(runs):
    have = [d for d in runs if d.get("rows")]
    if not have:
        print("\n(판정 행이 저장된 파일이 없어 정확도 표를 만들 수 없습니다)")
        return
    print("\n=== grounded 판정 정확도 — 판단 하나만 비교 ===")
    allr = []
    for d in have:
        rows = d["rows"]
        j = sum(1 for r in rows if r["jev"] == truth(r))
        l = sum(1 for r in rows if r["llm"] == truth(r))
        print(f"  {d['meta']['name']:22} 판단 모델 {j}/{len(rows)}   LLM {l}/{len(rows)}")
        allr += rows
    j = sum(1 for r in allr if r["jev"] == truth(r))
    l = sum(1 for r in allr if r["llm"] == truth(r))
    print(f"  {'합계':22} 판단 모델 {j}/{len(allr)}   LLM {l}/{len(allr)}")

    print("\n=== 확률이 0.5 근처인 구간 (판단 모델) ===")
    print("  경계 폭은 데이터를 보고 고른 값입니다. 폭을 바꿔 방향이 유지되는지 봅니다.")
    for w in (0.05, 0.10, 0.15, 0.20):
        band = [r for r in allr if abs(r["p_jev"] - 0.5) <= w]
        out = [r for r in allr if abs(r["p_jev"] - 0.5) > w]
        nb = sum(1 for r in band if r["jev"] == truth(r))
        no = sum(1 for r in out if r["jev"] == truth(r))
        print(f"  {0.5 - w:.2f}~{0.5 + w:.2f}   구간 안 {nb}/{len(band)}   밖 {no}/{len(out)}")

    wrong = [r for r in allr if r["jev"] != truth(r)]
    print(f"\n  판단 모델 오답 {len(wrong)}건의 확률: "
          + ", ".join(f"{r['p_jev']:.2f}" for r in sorted(wrong, key=lambda r: r['p_jev'])))


def disagreement_overlap(runs):
    """같은 셋을 두 번 잰 경우, 어긋난 문항이 겹치는지 본다."""
    def disagreed(d):
        if d.get("rows"):
            return {r["q"] for r in d["rows"] if r["jev"] != r["llm"]}
        return {r["q"] for r in d.get("disagree", [])}

    dev = [d for d in runs if d["meta"].get("split") == "dev"]
    if len(dev) < 2:
        return
    a, b = disagreed(dev[0]), disagreed(dev[1])
    print("\n=== 같은 개발셋을 두 번 잰 불일치 목록 ===")
    print(f"  {dev[0]['meta']['name']}: {len(a)}건   {dev[1]['meta']['name']}: {len(b)}건"
          f"   겹치는 문항 {len(a & b)}건")


def main():
    paths = sys.argv[1:] or BOOK
    runs = load(paths)
    latency_tables(runs)
    quality_tables(runs)
    disagreement_overlap(runs)


if __name__ == "__main__":
    main()
