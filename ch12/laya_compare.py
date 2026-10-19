# -*- coding: utf-8 -*-
"""12-6: 설계가 다른 판단 모델(Laya)로 갈아 끼우기 — zero-shot.

먼저 다른 터미널에서 가중치 리비전을 고정한 Laya 서버를 띄웁니다.

    pip install "laya[serve]==0.3.20"
    python ch12/laya_serve_pinned.py              책 12-6 의 리비전(55cf4c4), 127.0.0.1:8010

그다음 .env 의 TypeSafe 설정을 로컬 서버로 바꾸고 저장소 루트에서 실행합니다.

    TYPESAFE_API_KEY=local
    TYPESAFE_BASE_URL=http://127.0.0.1:8010

    python ch12/laya_compare.py --out laya_result.json

Laya 는 instructions 가 없는 질문을 422 로 거절하므로 12-3 과 같은 한 줄을 넣습니다.
--out 을 주면 문항마다 정답·예측·확률·confidence·선택된 체크포인트와 서버의
패키지·가중치 버전을 저장합니다. 책의 원자료는 ch12/results/book/ 에 있습니다.
"""
import argparse
import hashlib
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
LABELS = list(DEPARTMENTS)
DEPT_INS = "어느 부서가 처리해야 하는가?"
DEPT = {"d": Choice(instructions=DEPT_INS, criteria=DEPARTMENTS)}
GRID = (0.5, 0.7, 0.8, 0.9, 0.95)

REFUND_INS = "고객이 환불이나 결제 취소를 요구하고 있는가?"
REFUND_CRIT = {"true": "환불, 결제 취소, 금액 반환을 요구한다",
               "false": "환불을 언급만 하거나, 문의·불만·다른 요청이다"}


def base_url():
    return os.environ["TYPESAFE_BASE_URL"].rstrip("/")


def raw(body):
    """공식 SDK 응답에는 routing 이 없고, Noul 에는 labels 항목이 없어 HTTP 로 직접 보낸다."""
    req = urllib.request.Request(base_url() + "/v1/systemone",
                                 data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                 headers={"content-type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode("utf-8"))


def server_info():
    try:
        with urllib.request.urlopen(base_url() + "/pinned") as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return {"note": "고정 서버(/pinned)가 아님 — 가중치 리비전을 알 수 없음"}


def text_id(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def pct(xs, p):
    s = sorted(xs)
    return s[min(int(len(s) * p / 100), len(s) - 1)]


def run(client, data, split):
    rows = []
    for i, (text, truth, _) in enumerate(data):
        t0 = time.perf_counter()
        a = client.system_one(state=text, questions=DEPT).choices["d"]
        ms = (time.perf_counter() - t0) * 1000
        route = raw({"state": text, "questions": {"d": {"type": "choice", "instructions": DEPT_INS,
                                                        "criteria": DEPARTMENTS}}})["routing"]
        rows.append({"split": split, "idx": i, "text_id": text_id(text), "truth": truth, "pred": a.choice,
                     "ok": a.choice == truth, "conf": a.confidence, "probs": dict(a.probabilities),
                     "ms": ms, "checkpoint": route.get("model")})
    return rows


def brier(rows):
    return statistics.mean(sum((r["probs"].get(l, 0.0) - (1.0 if l == r["truth"] else 0.0)) ** 2
                               for l in LABELS) for r in rows)


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
    print(f"    전체 {overall:.3f}  최선의 게이트 {best[0]:.3f} (임계값 {best[1]}, 사후 탐색)  "
          f"버는 것 {best[0] - overall:+.3f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None, help="문항별 결과를 저장할 JSON 경로")
    a = ap.parse_args()

    info = server_info()
    print("서버:", info)
    with TypeSafeClient() as client:
        client.system_one(state="워밍업", questions=DEPT)
        dev, hold = run(client, DEV, "dev"), run(client, HOLDOUT, "holdout")

        th = next((c for c in GRID
                   if [r for r in dev if r["conf"] >= c]
                   and all(r["ok"] for r in dev if r["conf"] >= c)), None)
        for label, rows in (("개발셋", dev), ("검증셋", hold)):
            acc = sum(r["ok"] for r in rows) / len(rows)
            ms = [r["ms"] for r in rows]
            print(f"\n[{label}] 정확도 {acc:.3f}  Brier {brier(rows):.4f}  "
                  f"지연 P50 {pct(ms, 50):.0f} / P99 {pct(ms, 99):.0f} ms (로컬)")
            print(f"  예측 분포 {({k: sum(r['pred'] == k for r in rows) for k in LABELS})}  "
                  f"체크포인트 {({c: sum(r['checkpoint'] == c for r in rows) for c in {r['checkpoint'] for r in rows}})}")
            print("  임계값 표 (Laya 의 confidence — Jev 와 정의가 다르다)")
            gate_report(rows)
        print(f"\n개발셋에서 고른 무오류 임계값: {th if th is not None else '없음 — 게이트를 끈다'}")

        refund = []
        for i, (text, truth) in enumerate(REFUND_CASES):
            p_book = client.system_one(state=text, questions={
                "r": Noul(instructions=REFUND_INS, criteria=REFUND_CRIT)}).nouls["r"].noul
            p_ab = raw({"state": text, "questions": {"r": {
                "type": "noul", "instructions": REFUND_INS, "criteria": REFUND_CRIT,
                "labels": {"true": "A", "false": "B"}}}})["answers"]["r"]["noul"]
            refund.append({"idx": i, "text_id": text_id(text), "truth": truth, "p_book": p_book, "p_ab": p_ab})
        print(f"\n[5부 환불 판정 {len(refund)}건]")
        for label, key in (("책의 정의 그대로", "p_book"), ("라벨을 A·B로 바꿈 (별도 조건)", "p_ab")):
            ok = sum((r[key] >= 0.5) == r["truth"] for r in refund)
            fp = sum(r[key] >= 0.5 and not r["truth"] for r in refund)
            fn = sum(r[key] < 0.5 and r["truth"] for r in refund)
            print(f"  {label:24} 정확도 {ok / len(refund):.3f}  오탐 {fp}  놓침 {fn}")

    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump({"date": time.strftime("%Y-%m-%d"), "server": info, "instructions": DEPT_INS,
                       "dev_threshold": th, "dept": dev + hold, "refund": refund}, f, ensure_ascii=False, indent=1)
        print(f"\n저장: {a.out}")


if __name__ == "__main__":
    main()
