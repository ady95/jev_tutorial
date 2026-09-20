# -*- coding: utf-8 -*-
"""11-2 실습: 기권 신호 비교.

confidence 외의 신호가 더 나은 기권 판정을 주는가.
**모든 신호를 같은 호출에서 받는 것**이 핵심입니다.
따로 호출하면 샘플링 차이가 섞여 무엇을 비교하는지 알 수 없게 됩니다.
"""
import io
import json
import os
import statistics
import sys
import time

sys.path.insert(0, ".")
from _common import require_jev, warmup_jev
from dataset.inquiries import DEPARTMENTS, INQUIRIES

require_jev()
from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

QUESTIONS = {
    "department": Choice(criteria=DEPARTMENTS),
    # 아래는 전부 '판단에 대해 다시 묻는' 메타 질문입니다.
    # 책의 실측에서는 모두 분리력 +0.09 이하로 실패했습니다.
    # 여러분의 과제에서는 다를 수 있으니 직접 재보세요.
    "classifiable": Noul(
        instructions="이 문의가 네 부서 후보 중 하나에 명확히 해당하는가?",
        criteria={"true": "한 부서의 업무 범위에 분명히 들어간다",
                  "false": "두 부서에 걸쳐 있거나, 어느 후보에도 잘 맞지 않는다"}),
    "agreement": Noul(
        instructions="숙련된 상담원 두 명이 각자 분류한다면 같은 부서를 고를 것인가?",
        criteria={"true": "누가 봐도 같은 부서로 갈 문의다",
                  "false": "사람에 따라 다른 부서로 보낼 수 있는 문의다"}),
    "ambiguity": Score(criteria=[
        "한 부서에만 해당한다",
        "주로 한 부서지만 다른 부서도 조금 걸린다",
        "두 부서에 비슷하게 걸쳐 있다",
    ]),
}

# (신호 이름, 낮을수록 좋은 신호인가)
SIGNALS = [("confidence", False), ("margin", False),
           ("classifiable", False), ("agreement", False), ("ambiguity", True)]


def separation(rows, key, invert=False):
    """정답건 평균 - 오답건 평균. 클수록 좋은 기권 신호."""
    ok = statistics.mean(r[key] for r in rows if r["correct"])
    ng = statistics.mean(r[key] for r in rows if not r["correct"])
    return (ng - ok) if invert else (ok - ng)


def collect(client):
    rows = []
    warmup_jev(client, QUESTIONS["department"])
    for text, truth, amb in INQUIRIES:
        t0 = time.perf_counter()
        r = client.system_one(state=text, questions=QUESTIONS)
        d = r.choices["department"]
        p = sorted(d.probabilities.values(), reverse=True)
        rows.append({
            "text": text, "truth": truth, "ambiguous": amb,
            "pred": d.choice, "correct": d.choice == truth,
            "confidence": d.confidence,
            "margin": p[0] - (p[1] if len(p) > 1 else 0.0),
            "classifiable": r.nouls["classifiable"].noul,
            "agreement": r.nouls["agreement"].noul,
            "ambiguity": r.scores["ambiguity"].score,
            "probs": dict(d.probabilities),
            "ms": (time.perf_counter() - t0) * 1000,
            "model": r.model,
        })
    return rows


def main():
    with TypeSafeClient() as client:
        rows = collect(client)

    n = len(rows)
    print(f"모델 {rows[0]['model']}   정확도 {sum(r['correct'] for r in rows)/n:.3f}")
    print(f"평균 지연 {statistics.mean(r['ms'] for r in rows):.0f}ms (질문 {len(QUESTIONS)}개 동시)\n")

    print(f"{'신호':16} {'분리력':>9} {'정답평균':>10} {'오답평균':>10}")
    for key, inv in SIGNALS:
        ok = statistics.mean(r[key] for r in rows if r["correct"])
        ng = statistics.mean(r[key] for r in rows if not r["correct"])
        print(f"{key:16} {separation(rows, key, inv):+9.3f} {ok:10.3f} {ng:10.3f}")

    print("\n[동일 수용 건수에서의 신뢰도]")
    header = f"{'수용':>5} "
    for key, _ in SIGNALS:
        header += f"{key:>14}"
    print(header)
    for k in (50, 45, 40, 37, 30):
        if k > n:
            continue
        line = f"{k:5d} "
        for key, inv in SIGNALS:
            top = sorted(rows, key=lambda r: r[key], reverse=not inv)[:k]
            line += f"{sum(r['correct'] for r in top)/k:14.3f}"
        print(line)

    print("\n분리력이 0에 가까운 신호는 기권 판정에 쓸 수 없습니다.")
    print("책의 실측에서는 확률 분포에서 파생된 값(confidence, margin)만 작동했습니다.")

    os.makedirs("out", exist_ok=True)
    json.dump({"n": n, "rows": rows},
              io.open("out/abstain_signals.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("\n저장 -> out/abstain_signals.json")


if __name__ == "__main__":
    main()
