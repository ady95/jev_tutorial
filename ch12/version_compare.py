# -*- coding: utf-8 -*-
"""12-7: 같은 Jev의 두 버전을 같은 세션에서 번갈아 재기.

    python ch12/version_compare.py                          jev-1.13.0 대 jev-1.14.0, 3회
    python ch12/version_compare.py --runs 1 --limit 10      배선 확인

두 모델을 회차마다 번갈아 불러, 시각에 따른 흔들림이 한쪽 버전에 몰리지 않게 합니다.
책의 12-7 원자료는 ch12/results/book/v114_2026-10-19.json 입니다.
"""
import argparse
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv

load_dotenv()
from typesafe_sdk import Choice, Noul, TypeSafeClient

from dataset.holdout import HOLDOUT
from dataset.inquiries import INQUIRIES as DEV
from dataset.refund import REFUND_CASES

LABELS = ["billing", "technical", "sales", "other"]
DEPARTMENTS = {
    "billing": "요금, 결제, 환불, 세금계산서 관련",
    "technical": "오류, 장애, 사용법, 연동 문제",
    "sales": "구매 상담, 견적, 요금제 문의",
    "other": "위 어디에도 해당하지 않음",
}
DEPT = {"d": Choice(criteria=DEPARTMENTS)}                       # 4부·9부와 같은 질문
REFUND = {"r": Noul(instructions="고객이 환불이나 결제 취소를 요구하고 있는가?",
                    criteria={"true": "환불, 결제 취소, 금액 반환을 요구한다",
                              "false": "환불을 언급만 하거나, 문의·불만·다른 요청이다"})}
GRID = (0.5, 0.7, 0.8, 0.9, 0.95)


def classify(client, model, data):
    out = []
    for text, truth, _ in data:
        r = client.system_one(state=text, questions=DEPT, model=model)
        a = r.choices["d"]
        out.append({"truth": truth, "pred": a.choice, "conf": a.confidence,
                    "probs": dict(a.probabilities), "model": r.model})
    return out


def acc(rows):
    return sum(r["pred"] == r["truth"] for r in rows) / len(rows)


def brier(rows):
    return statistics.mean(sum((r["probs"].get(l, 0) - (l == r["truth"])) ** 2 for l in LABELS) for r in rows)


def pick(rows):
    """개발셋에서만 — 게이트 구간에서 무오류인 가장 낮은 임계값. 없으면 None."""
    for th in GRID:
        g = [r for r in rows if r["conf"] >= th]
        if g and all(r["pred"] == r["truth"] for r in g):
            return th
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs=2, default=["jev-1.13.0", "jev-1.14.0"])
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", default="version_compare_result.json")
    a = ap.parse_args()
    dev, hold = DEV[:a.limit], HOLDOUT[:a.limit]

    res = {m: {"dev": [], "holdout": [], "refund": []} for m in a.models}
    with TypeSafeClient() as client:
        for m in a.models:
            client.system_one(state="워밍업", questions=DEPT, model=m)
        for run in range(a.runs):
            for m in (a.models if run % 2 == 0 else a.models[::-1]):   # 회차마다 순서를 바꾼다
                res[m]["dev"].append(classify(client, m, dev))
                res[m]["holdout"].append(classify(client, m, hold))
                res[m]["refund"].append([
                    (client.system_one(state=t, questions=REFUND, model=m).nouls["r"].noul >= 0.5) == y
                    for t, y in REFUND_CASES])

    for m in a.models:
        th = pick(res[m]["dev"][0])
        models = sorted({r["model"] for split in ("dev", "holdout") for run in res[m][split] for r in run})
        print(f"\n[{m}]  응답 모델 {models}  개발셋에서 고른 임계값 {th}")
        for split in ("dev", "holdout"):
            accs = [acc(x) for x in res[m][split]]
            gates = []
            for x in res[m][split]:
                g = [r for r in x if th is not None and r["conf"] >= th]
                gates.append(f"{len(g)}건/{sum(r['pred'] == r['truth'] for r in g) / len(g):.3f}" if g else "0건")
            print(f"  {split:8} 정확도 {statistics.mean(accs):.3f} ({min(accs):.3f}~{max(accs):.3f})  "
                  f"Brier {statistics.mean(brier(x) for x in res[m][split]):.4f}  게이트 {gates}")
        print(f"  환불 20건 정확도 {[sum(x) / len(x) for x in res[m]['refund']]}")
        diff = max(abs(r["conf"] - (4 * max(r["probs"].values()) - 1) / 3)
                   for split in ("dev", "holdout") for run in res[m][split] for r in run)
        print(f"  confidence 와 (4·p_max − 1)/3 의 최대 차이 {diff:.4f}")

    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(f"\n저장: {a.out}")


if __name__ == "__main__":
    main()
