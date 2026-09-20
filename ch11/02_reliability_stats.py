# -*- coding: utf-8 -*-
"""11-3 실습: 신뢰도를 숫자로 방어하기.

측정값과 '주장 가능한 하한'을 구분합니다.
API 호출 없이 계산만 합니다. 먼저 ch04/calibration.py 를 실행하세요.
"""
import io
import json
import math
import os
import sys

sys.path.insert(0, ".")

SRC = "out/calibration.json"


def rule_of_three(n):
    """무오류 n건일 때 95% 신뢰수준 오류율 상한 (근사)."""
    return 3 / n if n else 1.0


def wilson_lower(successes, n, z=1.96):
    """95% 신뢰수준에서 실제 성공률의 하한."""
    if n == 0:
        return 0.0
    p = successes / n
    d = 1 + z * z / n
    center = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max((center - margin) / d, 0.0)


def samples_needed(target_reliability):
    """목표 신뢰도를 주장하는 데 필요한 무오류 건수."""
    return math.ceil(3 / (1 - target_reliability))


def reliability_report(rows, thresholds=(0.5, 0.7, 0.8, 0.9, 0.95)):
    n_all = len(rows)
    print(f"{'임계값':>7} {'수용':>6} {'coverage':>10} {'측정 신뢰도':>13} {'주장 가능 하한':>15}")
    for th in thresholds:
        kept = [r for r in rows if r["conf"] >= th]
        if not kept:
            continue
        ok = sum(r["correct"] for r in kept)
        n = len(kept)
        measured = ok / n
        claimable = (1 - rule_of_three(n)) if ok == n else wilson_lower(ok, n)
        print(f"  {th:5.2f} {n:6d} {n/n_all:10.1%} {measured:13.3f} {claimable:15.3f}")


def main():
    if not os.path.exists(SRC):
        sys.exit(f"{SRC} 가 없습니다. 먼저 python ch04/calibration.py 를 실행하세요.")
    rows = json.load(io.open(SRC, encoding="utf-8"))["rows"]

    print("[임계값별 측정값 vs 주장 가능한 하한]\n")
    reliability_report(rows)
    print("\n오른쪽 열이 실제로 방어할 수 있는 숫자입니다. 측정값보다 한참 낮습니다.")

    print("\n[목표 신뢰도별 필요 표본]\n")
    print(f"{'목표':>8} {'필요한 무오류 건수':>20}")
    for target in (0.95, 0.98, 0.99, 0.995, 0.999):
        print(f"{target:8.3f} {samples_needed(target):20d}")

    gate = [r for r in rows if r["conf"] >= 0.90]
    ok = sum(r["correct"] for r in gate)
    print(f"\n[이 평가셋의 결론]")
    print(f"  게이트 통과 {len(gate)}건, 오류 {len(gate)-ok}건")
    if ok == len(gate):
        print(f"  측정 신뢰도 1.000")
        print(f"  주장 가능한 신뢰도 {1 - rule_of_three(len(gate)):.3f}")
        print(f"  99%를 주장하려면 {samples_needed(0.99)}건 무오류가 필요합니다")
    else:
        print(f"  측정 신뢰도 {ok/len(gate):.3f}")
        print(f"  주장 가능한 하한 {wilson_lower(ok, len(gate)):.3f}")


if __name__ == "__main__":
    main()
