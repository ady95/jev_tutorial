# -*- coding: utf-8 -*-
"""04-2, 04-3 차트: Reliability Diagram, Risk-Coverage.

먼저 ch04/calibration.py 를 실행해 out/calibration.json 을 만드세요.
"""
import io
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager, rcParams

sys.path.insert(0, ".")

INK, MUTED, DATA, ACCENT = "#111827", "#64748B", "#0284C7", "#D97706"
for cand in ["Malgun Gothic", "AppleGothic", "NanumGothic", "Noto Sans KR"]:
    if any(f.name == cand for f in font_manager.fontManager.ttflist):
        rcParams["font.family"] = cand
        break
rcParams["axes.unicode_minus"] = False

SRC = "out/calibration.json"
if not os.path.exists(SRC):
    sys.exit("out/calibration.json 이 없습니다. 먼저 python ch04/calibration.py 를 실행하세요.")

d = json.load(io.open(SRC, encoding="utf-8"))


def style(ax):
    ax.set_facecolor("white")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
        ax.spines[s].set_linewidth(1)
    ax.tick_params(colors=MUTED, labelsize=10, length=4)
    ax.grid(True, color="#E2E8F0", linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_color(INK)


def reliability():
    bins = [b for b in d["bins"] if b["n"]]
    fig, ax = plt.subplots(figsize=(9, 5.6), dpi=100)
    fig.patch.set_facecolor("white")
    style(ax)

    ax.plot([0, 1], [0, 1], linestyle="--", linewidth=2, color=MUTED, zorder=2)
    ax.annotate("완벽히 보정된 선 (confidence = 정확도)", xy=(0.52, 0.52),
                xytext=(0.62, 0.26), color=MUTED, fontsize=10, ha="left",
                arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=1), zorder=2)

    xs = [b["conf"] for b in bins]
    ys = [b["acc"] for b in bins]
    ns = [b["n"] for b in bins]
    # 구간을 선으로 잇지 않습니다. 작은 구간이 크게 출렁이는 것처럼 보입니다.
    ax.scatter(xs, ys, s=[70 + n * 20 for n in ns], color=DATA, zorder=4,
               edgecolors="white", linewidths=2)
    ax.text(0.27, 1.07, "점 크기 = 그 구간에 들어간 문의 수",
            color=MUTED, fontsize=10, ha="left", va="center")
    for x, y, n in zip(xs, ys, ns):
        off = 16 if y >= x else -24
        ax.annotate(f"{n}건", (x, y), textcoords="offset points",
                    xytext=(0, off), ha="center", color=INK, fontsize=10, zorder=5)

    ax.set_xlim(0.25, 1.05)
    ax.set_ylim(-0.05, 1.12)
    ax.set_xlabel("모델이 말한 confidence (구간 평균)", color=INK, fontsize=11, labelpad=10)
    ax.set_ylabel("실제 정확도", color=INK, fontsize=11, labelpad=10)
    ax.set_title(f"Reliability Diagram — 문의 {d['n']}건 (ECE {d['ece']:.3f})",
                 color=INK, fontsize=13, pad=16, loc="left")
    fig.tight_layout()
    fig.savefig("out/reliability.png", facecolor="white")
    plt.close(fig)
    print("saved -> out/reliability.png")


def risk_coverage():
    rc = d["risk_coverage"]
    fig, ax = plt.subplots(figsize=(9, 5.6), dpi=100)
    fig.patch.set_facecolor("white")
    style(ax)

    cov = [r["coverage"] * 100 for r in rc]
    risk = [r["risk"] * 100 for r in rc]
    ax.plot(cov, risk, linewidth=2, color=DATA, zorder=3, solid_capstyle="round")
    ax.scatter(cov, risk, s=90, color=DATA, zorder=4, edgecolors="white", linewidths=2)

    zero = [r for r in rc if r["risk"] == 0]
    best = max(zero, key=lambda r: r["coverage"]) if zero else None

    for r, x, y in zip(rc, cov, risk):
        if best and r["threshold"] == best["threshold"]:
            continue
        ax.annotate(f"{r['threshold']:.2f}", (x, y), textcoords="offset points",
                    xytext=(0, 13), ha="center", color=MUTED, fontsize=10, zorder=5)

    if best:
        bx, by = best["coverage"] * 100, 0.0
        ax.scatter([bx], [by], s=200, color=ACCENT, zorder=6,
                   edgecolors="white", linewidths=2.5)
        ax.annotate(f"임계값 {best['threshold']:.2f}\n자동화 {bx:.0f}% · 오류 0%",
                    (bx, by), textcoords="offset points", xytext=(-58, 62),
                    ha="center", color=ACCENT, fontsize=11, zorder=7,
                    arrowprops=dict(arrowstyle="-", color=ACCENT, linewidth=1.5))

    ax.set_xlabel("자동 처리 비율 (%)  ← 점 옆 숫자는 confidence 임계값",
                  color=INK, fontsize=11, labelpad=10)
    ax.set_ylabel("자동 처리한 건의 오류율 (%)", color=INK, fontsize=11, labelpad=10)
    ax.set_title("Risk-Coverage — 임계값을 올리면 얼마나 포기하고 얼마나 안전해지는가",
                 color=INK, fontsize=13, pad=16, loc="left")
    fig.tight_layout()
    fig.savefig("out/risk_coverage.png", facecolor="white")
    plt.close(fig)
    print("saved -> out/risk_coverage.png")


if __name__ == "__main__":
    os.makedirs("out", exist_ok=True)
    reliability()
    risk_coverage()
