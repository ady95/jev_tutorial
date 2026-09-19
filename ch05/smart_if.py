# -*- coding: utf-8 -*-
"""05-1 실습: 규칙 엔진 vs 판단 — 환불 요구 판정.

규칙에 예외를 추가해도 정확도가 개선되지 않는 현상을 확인합니다.
"""
import sys
import time

sys.path.insert(0, ".")
from _common import require_jev, warmup_jev

require_jev()
from typesafe_sdk import Noul, TypeSafeClient

# (문장, 실제로 환불을 요구하는가)
CASES = [
    ("전액 환불해주세요", True),
    ("결제 취소 부탁드립니다", True),
    ("환불 처리 언제 되나요? 신청한 지 2주 됐습니다", True),
    ("잘못 결제했어요. 취소해주세요", True),
    ("구독 해지하고 남은 금액 돌려주세요", True),
    ("이번 건은 무를게요. 돈 돌려받고 싶습니다", True),
    ("당장 해지하고 전액 환불 안 해주면 신고하겠습니다", True),
    ("중복 결제된 건 돌려주시면 됩니다", True),
    ("환불은 안 해주셔도 되고요, 그냥 원인만 알려주세요", False),
    ("환불 정책이 어떻게 되는지 궁금합니다", False),
    ("환불 안 받을 테니 기능만 고쳐주세요", False),
    ("예전에 환불받은 적 있는데 그때 참 친절하셨어요", False),
    ("환불 규정 페이지 링크가 깨져 있습니다", False),
    ("돈 다시 넣어주세요", True),
    ("결제한 거 무효로 해주실 수 있나요", True),
    ("청구된 금액 취소 부탁합니다", True),
    ("로그인이 안 됩니다", False),
    ("견적서 보내주세요", False),
    ("서비스 잘 쓰고 있습니다", False),
    ("비밀번호를 바꾸고 싶습니다", False),
]

KEYWORDS = ["환불", "취소", "돌려", "반환"]
NEGATIONS = ["안 해", "안해", "필요 없", "괜찮"]

REFUND = Noul(
    instructions="고객이 환불이나 결제 취소를 요구하고 있는가?",
    criteria={"true": "환불이나 결제 취소를 실제로 요청하고 있다",
              "false": "가능 여부나 정책을 묻기만 하거나, 환불을 원하지 않거나, 무관한 내용이다"})


def rule_simple(text):
    return any(k in text for k in KEYWORDS)


def rule_with_negation(text):
    if not any(k in text for k in KEYWORDS):
        return False
    return not any(n in text for n in NEGATIONS)


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
    print("\n  ↑ 예외를 추가해도 정확도가 같습니다. 오탐이 놓침으로 옮겨갔을 뿐입니다.")

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
