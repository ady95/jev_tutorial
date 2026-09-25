# -*- coding: utf-8 -*-
"""12-6: 설계가 다른 판단 모델(Laya)로 갈아 끼우기 — zero-shot.

먼저 로컬에서 laya 서버를 띄웁니다 (다른 터미널).

    pip install "laya[serve]"
    LAYA_HOST=127.0.0.1 LAYA_PORT=8010 LAYA_DEVICE=cpu laya-serve

그다음 .env 의 TypeSafe 설정을 로컬 서버로 바꾸고 저장소 루트에서 실행합니다.

    TYPESAFE_API_KEY=local
    TYPESAFE_BASE_URL=http://127.0.0.1:8010

    python ch12/laya_compare.py

책의 12-6 은 laya 0.3.20, 가중치 convaiinnovations/laya 리비전 55cf4c4 로 쟀습니다.
Laya 는 instructions 가 없는 질문을 422 로 거절하므로 12-3 과 같은 한 줄을 넣습니다.
"""
import json
import os
import statistics
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv

load_dotenv()
from typesafe_sdk import Choice, Noul, TypeSafeClient

from dataset.holdout import HOLDOUT
from dataset.inquiries import INQUIRIES as DEV
from dataset.refund import REFUND_CASES

DEPARTMENTS = {
    "billing": "요금, 결제, 환불, 세금계산서 관련",
    "technical": "오류, 장애, 사용법, 연동 문제",
    "sales": "구매 상담, 견적, 요금제 문의",
    "other": "위 어디에도 해당하지 않음",
}
DEPT = {"d": Choice(instructions="어느 부서가 처리해야 하는가?", criteria=DEPARTMENTS)}
GRID = (0.5, 0.7, 0.8, 0.9, 0.95)

REFUND_INS = "고객이 환불이나 결제 취소를 요구하고 있는가?"
REFUND_CRIT = {"true": "환불, 결제 취소, 금액 반환을 요구한다",
               "false": "환불을 언급만 하거나, 문의·불만·다른 요청이다"}


def raw(body):
    """공식 SDK 의 Noul 에는 labels 항목이 없어 HTTP 로 직접 보낸다."""
    url = os.environ["TYPESAFE_BASE_URL"].rstrip("/") + "/v1/systemone"
    req = urllib.request.Request(url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                 headers={"content-type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode("utf-8"))


def pct(xs, p):
    s = sorted(xs)
    return s[min(int(len(s) * p / 100), len(s) - 1)]


def brier(rows):
    return statistics.mean(sum((r["probs"].get(l, 0.0) - (1.0 if l == r["truth"] else 0.0)) ** 2
                               for l in DEPARTMENTS) for r in rows)


def run(client, data):
    rows = []
    for text, truth, _ in data:
        t0 = time.perf_counter()
        a = client.system_one(state=text, questions=DEPT).choices["d"]
        rows.append({"truth": truth, "pred": a.choice, "ok": a.choice == truth,
                     "conf": a.confidence, "probs": dict(a.probabilities),
                     "ms": (time.perf_counter() - t0) * 1000})
    return rows


def gate_report(rows):
    """12-5 의 gate_is_usable 과 같은 계산. 10건 미만 구간은 판단에서 뺀다."""
    overall = sum(r["ok"] for r in rows) / len(rows)
    best = (0.0, None)
    for th in GRID:
        g = [r for r in rows if r["conf"] >= th]
        rel = sum(r["ok"] for r in g) / len(g) if g else None
        shown = "-" if rel is None else f"{rel:.3f}"
        print(f"    {th:.2f}  통과 {len(g):2d}건  coverage {len(g) / len(rows):5.1%}  신뢰도 {shown}")
        if len(g) >= 10 and rel is not None and rel > best[0]:
            best = (rel, th)
    print(f"    전체 {overall:.3f}  최선의 게이트 {best[0]:.3f} (임계값 {best[1]})  "
          f"버는 것 {best[0] - overall:+.3f}")


def main():
    with TypeSafeClient() as client:
        client.system_one(state="워밍업", questions=DEPT)
        dev, hold = run(client, DEV), run(client, HOLDOUT)

        # 개발셋에서 무오류 임계값을 고른다 (9부 정책). 없으면 게이트를 끈다
        th = next((c for c in GRID
                   if [r for r in dev if r["conf"] >= c]
                   and all(r["ok"] for r in dev if r["conf"] >= c)), None)

        for label, rows in (("개발셋", dev), ("검증셋", hold)):
            acc = sum(r["ok"] for r in rows) / len(rows)
            ms = [r["ms"] for r in rows]
            dist = {k: sum(r["pred"] == k for r in rows) for k in DEPARTMENTS}
            print(f"\n[{label}] 정확도 {acc:.3f}  Brier {brier(rows):.4f}  "
                  f"지연 P50 {pct(ms, 50):.0f} / P99 {pct(ms, 99):.0f} ms (로컬)")
            print(f"  예측 분포 {dist}")
            print("  임계값 표 (Laya 의 confidence — Jev 와 정의가 다르다)")
            gate_report(rows)
        print(f"\n개발셋에서 고른 무오류 임계값: {th if th is not None else '없음 — 게이트를 끈다'}")

        print(f"\n[5부 환불 판정 {len(REFUND_CASES)}건]")
        for label, labels in (("책의 정의 그대로", None), ("라벨을 A·B로 바꿈 (별도 조건)", {"true": "A", "false": "B"})):
            ok = fp = fn = 0
            for text, truth in REFUND_CASES:
                if labels is None:
                    p = client.system_one(state=text, questions={
                        "r": Noul(instructions=REFUND_INS, criteria=REFUND_CRIT)}).nouls["r"].noul
                else:
                    p = raw({"state": text, "questions": {"r": {
                        "type": "noul", "instructions": REFUND_INS, "criteria": REFUND_CRIT,
                        "labels": labels}}})["answers"]["r"]["noul"]
                ok += (p >= 0.5) == truth
                fp += p >= 0.5 and not truth
                fn += p < 0.5 and truth
            print(f"  {label:24} 정확도 {ok / len(REFUND_CASES):.3f}  오탐 {fp}  놓침 {fn}")


if __name__ == "__main__":
    main()
