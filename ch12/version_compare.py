# -*- coding: utf-8 -*-
"""12-7: 같은 Jev의 두 버전을 같은 세션에서 번갈아 재기 (API 호출).

    python ch12/version_compare.py                      책의 12-7 전체 실험 (두 모델 x 3회)
    python ch12/version_compare.py --runs 1 --limit 5   배선 확인

재는 것 — 책 12-7 의 표 전부:
  부서 분류  instructions 없음(4부·9부 조건) / 있음(12-4 조건), 개발·검증셋
  환불 판정  5부의 20건
  지연       질문 1·3·6개 (3-4 와 같은 묶음)
두 모델을 회차마다 순서를 바꿔 번갈아 불러, 시각에 따른 흔들림이 한쪽에 몰리지 않게 합니다.
결과는 --out 파일에 건별로 남고, ch12/version_analyze.py 가 그 파일로 표를 다시 냅니다.
책의 원자료는 ch12/results/book/v114_2026-10-19.json 입니다.
"""
import argparse
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv

load_dotenv()
from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

from dataset.holdout import HOLDOUT
from dataset.inquiries import INQUIRIES as DEV
from dataset.refund import REFUND_CASES

DEPARTMENTS = {
    "billing": "요금, 결제, 환불, 세금계산서 관련",
    "technical": "오류, 장애, 사용법, 연동 문제",
    "sales": "구매 상담, 견적, 요금제 문의",
    "other": "위 어디에도 해당하지 않음",
}
VARIANTS = {
    "plain": {"d": Choice(criteria=DEPARTMENTS)},
    "instr": {"d": Choice(instructions="어느 부서가 처리해야 하는가?", criteria=DEPARTMENTS)},
}
REFUND = {"r": Noul(instructions="고객이 환불이나 결제 취소를 요구하고 있는가?",
                    criteria={"true": "환불, 결제 취소, 금액 반환을 요구한다",
                              "false": "환불을 언급만 하거나, 문의·불만·다른 요청이다"})}
DEPT = Choice(criteria=DEPARTMENTS)
QSETS = {
    1: {"d": DEPT},
    3: {"d": DEPT, "refund": Noul(instructions="환불 요구인가?"),
        "urg": Score(criteria=["급하지 않음", "보통", "급함", "매우 급함"])},
    6: {"d": DEPT, "refund": Noul(instructions="환불 요구인가?"),
        "urg": Score(criteria=["급하지 않음", "보통", "급함", "매우 급함"]),
        "spam": Noul(instructions="스팸인가?"), "human": Noul(instructions="사람이 검토해야 하는가?"),
        "sentiment": Score(criteria=["차분함", "약간 불만", "화남", "매우 화남"])},
}
LAT_Q = "쓰던 요금제가 저한테 안 맞는 것 같아요. 어떻게 하죠?"


def classify(client, model, data, questions):
    rows = []
    for text, truth, _ in data:
        t0 = time.perf_counter()
        r = client.system_one(state=text, questions=questions, model=model)
        a = r.choices["d"]
        rows.append({"truth": truth, "pred": a.choice, "conf": a.confidence,
                     "probs": dict(a.probabilities), "ms": (time.perf_counter() - t0) * 1000,
                     "model": r.model, "in_tok": r.usage.input_tokens})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs=2, default=["jev-1.13.0", "jev-1.14.0"])
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--limit", type=int, default=None, help="셋마다 앞 N건만 (배선 확인용)")
    ap.add_argument("--out", default="version_compare_result.json")
    a = ap.parse_args()
    dev, hold = DEV[:a.limit], HOLDOUT[:a.limit]
    refund = REFUND_CASES[:a.limit]

    out = {"date": time.strftime("%Y-%m-%d"), "models": a.models, "dept": {}, "refund": {}, "latency": {}}
    with TypeSafeClient() as client:
        for m in a.models:
            client.system_one(state="워밍업", questions=VARIANTS["plain"], model=m)
        for run in range(1, a.runs + 1):
            for m in (a.models if run % 2 else a.models[::-1]):      # 회차마다 순서를 바꾼다
                for var, qs in VARIANTS.items():
                    for split, data in (("dev", dev), ("holdout", hold)):
                        key = f"{m}|{var}|{split}|{run}"
                        out["dept"][key] = classify(client, m, data, qs)
                        acc = sum(r["pred"] == r["truth"] for r in out["dept"][key]) / len(data)
                        print(f"{key:36} 정확도 {acc:.3f}", flush=True)
                out["refund"][f"{m}|{run}"] = [
                    {"text": t, "truth": y, "p": client.system_one(state=t, questions=REFUND, model=m).nouls["r"].noul}
                    for t, y in refund]
        for m in a.models:
            for k, qs in QSETS.items():
                times = []
                for _ in range(5):
                    t0 = time.perf_counter()
                    r = client.system_one(state=LAT_Q, questions=qs, model=m)
                    times.append((time.perf_counter() - t0) * 1000)
                out["latency"][f"{m}|{k}"] = {"ms": times, "in_tok": r.usage.input_tokens, "models": [r.model]}
                print(f"{m} 질문 {k}개  중앙값 {statistics.median(times):.0f}ms", flush=True)

    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\n저장: {a.out}\n표 보기: python ch12/version_analyze.py {a.out}")


if __name__ == "__main__":
    main()
