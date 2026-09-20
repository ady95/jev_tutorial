# -*- coding: utf-8 -*-
"""11-4 실습: 표본 점검 설계.

표본 점검은 오류를 잡는 장치가 아니라 신뢰도를 재는 장치입니다.
목적을 헷갈리면 표본 설계가 틀립니다.

API 호출 없이 계산과 시뮬레이션만 합니다.
"""
import io
import json
import math
import os
import random
import sys

sys.path.insert(0, ".")

SRC = "out/calibration.json"
AUDIT_RATE = 0.02


def sample_size(expected_error_rate, precision, z=1.96):
    """오류율을 +-precision 정밀도로 추정하는 데 필요한 표본 수."""
    p = max(expected_error_rate, 0.005)
    return math.ceil(z * z * p * (1 - p) / (precision * precision))


def build_audit_queue(gated, daily_budget=12, seed=0):
    """점검 대상을 세 갈래로 나눠 뽑는다.

    무작위만 오류율 추정에 쓴다. 나머지는 의도적으로 편향된 표본이라
    통계에 섞으면 추정이 망가진다.
    """
    rng = random.Random(seed)
    n_random = max(1, int(daily_budget * 0.5))
    n_border = max(1, int(daily_budget * 0.3))
    n_odd = max(1, int(daily_budget * 0.2))

    random_sample = rng.sample(gated, min(n_random, len(gated)))
    borderline = sorted(gated, key=lambda r: r["conf"])[:n_border]
    odd = sorted(gated, key=lambda r: abs(r["margin"] - r["conf"]),
                 reverse=True)[:n_odd]
    return {"random": random_sample, "borderline": borderline, "odd": odd}


def main():
    if not os.path.exists(SRC):
        sys.exit(f"{SRC} 가 없습니다. 먼저 python ch04/calibration.py 를 실행하세요.")
    rows = json.load(io.open(SRC, encoding="utf-8"))["rows"]

    # margin 이 없으면 probs 에서 계산
    for r in rows:
        if "margin" not in r:
            p = sorted(r["probs"].values(), reverse=True)
            r["margin"] = p[0] - (p[1] if len(p) > 1 else 0.0)

    print("[필요 표본 수]\n")
    print(f"{'예상 오류율':>11} {'정밀도':>8} {'필요 표본':>10}")
    for err, prec in ((0.05, 0.02), (0.02, 0.01), (0.01, 0.01), (0.01, 0.005)):
        print(f"{err:11.1%} {prec:8.1%} {sample_size(err, prec):10d}")
    print("\n신뢰도가 높을수록 그것을 확인하는 데 더 많은 표본이 듭니다.")
    print("오류가 드물어서 세기 어렵기 때문입니다.\n")

    gated = [r for r in rows if r["conf"] >= 0.90]
    print(f"[점검 큐 구성]  게이트 통과 {len(gated)}건 중 하루 12건을 뽑는다\n")
    q = build_audit_queue(gated, daily_budget=12)
    for kind, items in q.items():
        label = {"random": "무작위 (오류율 추정용)",
                 "borderline": "경계 (간신히 통과한 건)",
                 "odd": "이례 (margin과 confidence가 어긋난 건)"}[kind]
        print(f"  {label} — {len(items)}건")
        for r in items[:3]:
            print(f"    conf={r['conf']:.2f} margin={r['margin']:.2f}  {r['text'][:32]}")

    print("\n[누적 시뮬레이션]  하루 600건 자동 처리, 2% 점검")
    daily_auto = 600
    daily_audit = int(daily_auto * AUDIT_RATE)
    print(f"{'기간':>8} {'점검 누적':>10} {'무오류라면 주장 가능한 신뢰도':>28}")
    for days, label in ((7, "1주"), (30, "1개월"), (90, "3개월"), (365, "1년")):
        n = daily_audit * days
        print(f"{label:>8} {n:10d} {1 - 3/n:28.4f}")

    print("\n무작위 표본만 위 계산에 씁니다. 경계·이례 표본은 문제를 빨리 찾는 용도입니다.")


if __name__ == "__main__":
    main()
