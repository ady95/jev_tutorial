# -*- coding: utf-8 -*-
"""05-1 실습: 규칙 엔진 vs 판단 — 환불 요구 판정.

규칙에 예외를 붙이면 오탐이 줄고 놓침이 느는 현상을 확인합니다.
평가셋과 규칙은 책 부록 D의 dataset_refund.py, refund_eval.py 와 같습니다.
"""
import sys
import time

sys.path.insert(0, ".")
from _common import require_jev, warmup_jev

require_jev()
from typesafe_sdk import Noul, TypeSafeClient

from dataset.refund import REFUND_CASES as CASES     # 책 05-1 표의 20건

NEGATIONS = ["안 해", "안해", "필요 없", "괜찮", "안 받"]

# 이 문구가 책 5부 표의 실측본이다. 조금만 바꿔도 20건 중 한 건의 판정이 뒤집힌다
REFUND = Noul(
    instructions="고객이 환불이나 결제 취소를 요구하고 있는가?",
    criteria={"true": "환불, 결제 취소, 금액 반환을 요구한다",
              "false": "환불을 언급만 하거나, 문의·불만·다른 요청이다"})


def rule_simple(text):
    return "환불" in text


def rule_with_negation(text):
    return "환불" in text and not any(n in text for n in NEGATIONS)


def evaluate(name, predict):
    tp = fp = tn = fn = 0
    wrong = []
    for text, truth in CASES:
        p = predict(text)
        if p and truth:
            tp += 1
        elif p and not truth:
            fp += 1
            wrong.append(("오탐", text))
        elif not p and truth:
            fn += 1
            wrong.append(("놓침", text))
        else:
            tn += 1
    n = len(CASES)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    print(f"\n[{name}]  정확도 {(tp+tn)/n:.3f}  정밀도 {prec:.3f}  "
          f"재현율 {rec:.3f}  F1 {f1:.3f}  (오탐 {fp} / 놓침 {fn})")
    for kind, text in wrong:
        print(f"    {kind}: {text}")


def main():
    evaluate("규칙: 키워드만", rule_simple)
    evaluate("규칙: 키워드 + 부정어 예외", rule_with_negation)
    print("\n  ↑ 정확도는 한 건 올랐지만, 오탐을 둘 줄이는 대신 놓침이 하나 늘었습니다.")

    with TypeSafeClient() as client:
        warmup_jev(client, REFUND)
        lat, probs = [], {}
        for text, _ in CASES:
            t0 = time.perf_counter()
            probs[text] = client.system_one(
                state=text, questions={"r": REFUND}).nouls["r"].noul
            lat.append((time.perf_counter() - t0) * 1000)

    for th in (0.5, 0.7, 0.9):
        evaluate(f"Jev (임계값 {th})", lambda t, _th=th: probs[t] >= _th)

    print(f"\nJev 평균 지연시간 {sum(lat)/len(lat):.0f}ms\n")
    print("확률 분포:")
    for text, truth in sorted(CASES, key=lambda c: -probs[c[0]]):
        print(f"  {probs[text]:.2f}  정답={'요구' if truth else '아님':4}  {text[:44]}")
    print("\n요구인 건과 아닌 건 사이가 비어 있으면 임계값 위치가 결과를 크게 바꾸지 않습니다.")


if __name__ == "__main__":
    main()
