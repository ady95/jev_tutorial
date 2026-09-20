# -*- coding: utf-8 -*-
"""11-5 실습: criteria를 고쳐 coverage를 넓힌다.

모델도 임계값도 코드도 그대로 두고 후보 설명만 바꿉니다.
책의 실측에서 이 방법이 유일하게 크게 작동했습니다.

고친 뒤 **반드시 전체를 다시 돌려** 새로 깨진 건을 확인하세요.
"""
import io
import json
import os
import sys
import time

sys.path.insert(0, ".")
from _common import require_jev, warmup_jev
from dataset.inquiries import DEPARTMENTS, INQUIRIES

require_jev()
from typesafe_sdk import Choice, TypeSafeClient

V1 = DEPARTMENTS

# 틀린 건들이 어디에 걸렸는지 보고 경계를 명시한 버전
V2 = {
    "billing": ("요금, 결제, 환불, 세금계산서, 영수증. "
                "청구 금액이나 사용량이 왜 이런지 묻는 것도 포함"),
    "technical": ("오류, 장애, 사용법, 연동 문제. "
                  "기능이 왜 안 되는지 원인을 묻는 것도 포함"),
    "sales": ("구매 상담, 견적, 요금제 선택, 우리 파트너 프로그램 가입 문의, "
              "계약 갱신, 타사에서 넘어오는 전환 지원"),
    "other": ("채용, 언론, 개인정보. 외부에서 들어온 제휴·광고 제안과 스팸, "
              "그 밖의 문의"),
}


def run(criteria, client, label):
    dept = Choice(criteria=criteria)
    warmup_jev(client, dept)
    rows = []
    for text, truth, amb in INQUIRIES:
        a = client.system_one(state=text, questions={"d": dept}).choices["d"]
        p = sorted(a.probabilities.values(), reverse=True)
        rows.append({"text": text, "truth": truth, "pred": a.choice,
                     "correct": a.choice == truth, "confidence": a.confidence,
                     "margin": p[0] - (p[1] if len(p) > 1 else 0.0)})
    acc = sum(r["correct"] for r in rows) / len(rows)
    print(f"[{label}] 정확도 {acc:.3f}")
    return rows


def coverage_at(rows, target, key="confidence"):
    """목표 신뢰도를 만족하는 최대 coverage."""
    best = None
    for th in sorted({round(r[key], 3) for r in rows}):
        kept = [r for r in rows if r[key] >= th]
        if not kept:
            continue
        acc = sum(r["correct"] for r in kept) / len(kept)
        if acc >= target and (best is None or len(kept) > best[1]):
            best = (th, len(kept), acc)
    return best


def compare_runs(before, after):
    fixed = [(a, b) for a, b in zip(before, after) if not a["correct"] and b["correct"]]
    broke = [(a, b) for a, b in zip(before, after) if a["correct"] and not b["correct"]]
    risky = [b for a, b in broke if b["confidence"] >= 0.85]
    return fixed, broke, risky


def main():
    with TypeSafeClient() as client:
        v1 = run(V1, client, "V1 원래 정의")
        v2 = run(V2, client, "V2 고친 정의")

    n = len(v1)
    print(f"\n{'':16} {'정확도':>8} {'0.95 기준 coverage':>20}")
    for label, rows in (("V1 원래 정의", v1), ("V2 고친 정의", v2)):
        acc = sum(r["correct"] for r in rows) / n
        b = coverage_at(rows, 0.95)
        s = f"{b[1]}건 {b[1]/n:.1%}" if b else "불가"
        print(f"{label:16} {acc:8.3f} {s:>20}")

    fixed, broke, risky = compare_runs(v1, v2)
    print(f"\n고침 {len(fixed)}건 / 망침 {len(broke)}건 / 순증 {len(fixed)-len(broke)}건")

    for a, b in fixed:
        print(f"  고침  정답={a['truth']:10} {a['pred']}({a['confidence']:.2f}) "
              f"-> {b['pred']}({b['confidence']:.2f})  {a['text'][:30]}")
    for a, b in broke:
        print(f"  망침  정답={a['truth']:10} {a['pred']}({a['confidence']:.2f}) "
              f"-> {b['pred']}({b['confidence']:.2f})  {a['text'][:30]}")

    if risky:
        print(f"\n  위험: 틀렸는데 confidence가 0.85 이상으로 올라간 건 {len(risky)}건")
        for r in risky:
            print(f"    conf={r['confidence']:.2f} 정답={r['truth']} 예측={r['pred']}  {r['text'][:30]}")
        print("  순증이 양수여도 이런 건이 있으면 신뢰도는 나빠질 수 있습니다.")

    print("\n[아직 틀린 건 (V2)]")
    for r in v2:
        if not r["correct"]:
            print(f"  conf={r['confidence']:.2f} 정답={r['truth']:10} 예측={r['pred']:10}  {r['text'][:34]}")
    print("\n남은 오류가 전부 낮은 confidence에 있고 사람도 갈릴 만한 내용이라면,")
    print("개선은 끝난 것입니다. 더 고치려 들면 멀쩡한 건을 깨뜨립니다.")

    os.makedirs("out", exist_ok=True)
    json.dump({"v1": v1, "v2": v2, "criteria_v1": V1, "criteria_v2": V2},
              io.open("out/improve_criteria.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("\n저장 -> out/improve_criteria.json")


if __name__ == "__main__":
    main()
