# benchmark.py — 9부의 표를 만든 기준 구현
"""9부 4파전 + 하이브리드. 책 9부의 표는 이 파일로 쟀다.

    python benchmark.py                   개발셋 1회 + 검증셋 3회
    python benchmark.py --holdout-runs 1
    python benchmark.py --limit 5         셋마다 앞 5건 (배선 확인용)

임계값 정책: 개발셋 1회에서 "무오류를 유지하는 가장 낮은 값"을 고르고, 그 값을
검증셋의 모든 회차에 그대로 쓴다. 검증셋 회차마다 다시 고르지 않는다.
"""
import argparse
import json
import re
import statistics
import time

from dotenv import load_dotenv
from openai import OpenAI
from typesafe_sdk import Choice, TypeSafeClient

try:                                    # 부록 D 를 그대로 저장한 경우
    from dataset_dev import DEV
    from dataset_holdout import HOLDOUT
except ImportError:                     # 예제 저장소
    from dataset.inquiries import INQUIRIES as DEV
    from dataset.holdout import HOLDOUT

load_dotenv()
SMALL, FRONTIER = "gpt-6-luna", "gpt-6-astra"      # 쓰실 모델로 바꾸세요

LABELS = ["billing", "technical", "sales", "other"]
VALID = "|".join(LABELS)
DEPARTMENTS = {
    "billing": "요금, 결제, 환불, 세금계산서 관련",
    "technical": "오류, 장애, 사용법, 연동 문제",
    "sales": "구매 상담, 견적, 요금제 문의",
    "other": "위 어디에도 해당하지 않음",
}
# 같은 정의: LLM 프롬프트와 Jev 의 criteria 에 위 설명을 똑같이 넣는다
PROMPT = ("다음 고객 문의를 아래 부서 중 하나로 분류하세요. 부서 이름 하나만 답하세요.\n\n"
          + "\n".join(f"- {k}: {v}" for k, v in DEPARTMENTS.items())
          + "\n\n문의: ")

# 후보 설명만 보고 쓴 키워드다. 오답 목록을 보고 늘리지 않았다.
# sales 를 billing 보다 먼저 봐야 "요금제"가 요금으로 새지 않는다.
RULES = [
    ("sales", ["견적", "요금제", "플랜", "도입", "구매", "계약", "상담"]),
    ("billing", ["결제", "환불", "요금", "청구", "세금계산서", "영수증", "카드", "인보이스"]),
    ("technical", ["오류", "에러", "장애", "연동", "API", "로그인", "사용법",
                   "안 됩니다", "안 돼"]),
]


def pct(xs, p):
    """p 백분위. 100건 이하에서 P99 는 최댓값 그 자체다."""
    s = sorted(xs)
    return s[min(int(len(s) * p / 100), len(s) - 1)]


def rule_run(texts):
    preds, lat = [], []
    for text in texts:
        t0 = time.perf_counter()
        pred = "other"
        for label, words in RULES:
            if any(w in text for w in words):
                pred = label
                break
        preds.append(pred)
        lat.append((time.perf_counter() - t0) * 1000)
    return preds, lat


def jev_run(texts, client):
    q = {"d": Choice(criteria=DEPARTMENTS)}
    client.system_one(state="워밍업", questions=q)          # 첫 호출 제외
    preds, lat, confs, probs, out_tok, models = [], [], [], [], [], []
    for text in texts:
        t0 = time.perf_counter()
        r = client.system_one(state=text, questions=q)
        lat.append((time.perf_counter() - t0) * 1000)
        a = r.choices["d"]
        preds.append(a.choice)
        confs.append(a.confidence)
        probs.append(dict(a.probabilities))
        out_tok.append(r.usage.output_tokens or 0)
        models.append(r.model)                             # 실제로 답한 모델
    return preds, lat, confs, probs, out_tok, models


def llm_run(texts, oa, model):
    oa.chat.completions.create(                            # 워밍업
        model=model, messages=[{"role": "user", "content": PROMPT + "테스트"}])
    preds, lat, fmt_err, out_tok, reason_tok, models = [], [], 0, [], [], []
    for text in texts:
        t0 = time.perf_counter()
        r = oa.chat.completions.create(
            model=model, messages=[{"role": "user", "content": PROMPT + text}])
        lat.append((time.perf_counter() - t0) * 1000)
        models.append(r.model)                             # 실제로 답한 모델
        out_tok.append(r.usage.completion_tokens)
        d = getattr(r.usage, "completion_tokens_details", None)
        d = (d if isinstance(d, dict) else d.model_dump()) if d else {}
        reason_tok.append(d.get("reasoning_tokens", 0) or 0)
        txt = (r.choices[0].message.content or "").strip()
        if re.fullmatch(rf"({VALID})\.?", txt):
            preds.append(txt.rstrip("."))
        else:
            fmt_err += 1                                   # 형식을 안 지킨 건
            m = re.search(VALID, txt)
            preds.append(m.group(0) if m else "other")
    return preds, lat, fmt_err, out_tok, reason_tok, models


def hybrid(jev_preds, jev_confs, llm_preds, threshold):
    """confidence가 임계값 이상이면 Jev 답을 쓰고, 아니면 LLM에 넘긴다."""
    return [j if c >= threshold else l
            for j, c, l in zip(jev_preds, jev_confs, llm_preds)]


def pick_threshold(preds, confs, truths, candidates=(0.5, 0.7, 0.8, 0.9, 0.95)):
    """개발셋에서만 부른다 — 게이트 구간에서 무오류를 유지하는 가장 낮은 값."""
    best = candidates[-1]
    for th in candidates:
        gate = [(p, t) for p, c, t in zip(preds, confs, truths) if c >= th]
        if gate and all(p == t for p, t in gate):
            best = th
            break
    return best


def brier(probs, truths):
    return statistics.mean(sum((p.get(l, 0.0) - (1.0 if l == t else 0.0)) ** 2
                               for l in LABELS) for p, t in zip(probs, truths))


def ece(confs, correct, n_bins=10):
    n, total = len(confs), 0.0
    for i in range(n_bins):
        lo, hi = i / n_bins, (i + 1) / n_bins
        idx = [k for k, c in enumerate(confs) if (lo < c <= hi) or (i == 0 and c == 0.0)]
        if idx:
            total += len(idx) / n * abs(statistics.mean(confs[k] for k in idx)
                                        - statistics.mean(correct[k] for k in idx))
    return total


def row(name, preds, truths, lat, fmt_err=0, out_tok=None, reason_tok=None):
    d = {"name": name, "acc": sum(p == t for p, t in zip(preds, truths)) / len(truths),
         "mean": statistics.mean(lat), "p50": statistics.median(lat),
         "p95": pct(lat, 95), "p99": pct(lat, 99), "fmt_err": fmt_err}
    if out_tok:
        d["out_tok"] = statistics.mean(out_tok)
    if reason_tok:
        d["reason_tok"] = statistics.mean(reason_tok)
    return d


def bench(dataset, label, oa, client, threshold=None):
    texts = [x for x, _, _ in dataset]
    truths = [y for _, y, _ in dataset]
    out = {"label": label, "rows": []}

    rp, rl = rule_run(texts)
    out["rows"].append(row("규칙 엔진", rp, truths, rl))
    jp, jl, jc, jprob, jo, jm = jev_run(texts, client)
    out["rows"].append(row("Jev 단독", jp, truths, jl, out_tok=jo))
    sp, sl, se, so, sr, sm = llm_run(texts, oa, SMALL)
    out["rows"].append(row(f"하위 티어 LLM ({SMALL})", sp, truths, sl, se, so, sr))
    fp, fl, fe, fo, fr, fm = llm_run(texts, oa, FRONTIER)
    out["rows"].append(row(f"프런티어 LLM ({FRONTIER})", fp, truths, fl, fe, fo, fr))
    out["models"] = sorted(set(jm + sm + fm))              # 응답에 찍힌 모델 이름

    if threshold is None:
        threshold = pick_threshold(jp, jc, truths)
    hp = hybrid(jp, jc, fp, threshold)
    hl = [j if c >= threshold else j + f
          for j, c, f in zip(jl, jc, fl)]          # 게이트 미통과 건은 두 번 부른다
    out["rows"].append(row("Jev + 프런티어", hp, truths, hl))

    gate = [p == t for p, c, t in zip(jp, jc, truths) if c >= threshold]
    out.update(threshold=threshold, gated=len(gate),
               gate_reliability=sum(gate) / len(gate) if gate else None,
               llm_call_pct=1 - len(gate) / len(texts),
               jev_brier=brier(jprob, truths),
               jev_ece=ece(jc, [p == t for p, t in zip(jp, truths)]),
               items=[{"truth": t, "rule": r, "jev": j, "conf": c, "small": s,
                       "frontier": f, "hybrid": h}      # 건별 예측 — 어느 문항에서 갈렸는지 본다
                      for t, r, j, c, s, f, h in zip(truths, rp, jp, jc, sp, fp, hp)])
    return out


def show(r):
    print(f"\n[{r['label']}]  임계값 {r['threshold']}  게이트 통과 {r['gated']}건  "
          f"게이트 신뢰도 {r['gate_reliability']}  LLM 호출 {r['llm_call_pct']:.1%}  "
          f"Jev Brier {r['jev_brier']:.4f}  ECE {r['jev_ece']:.4f}")
    print(f"{'방식':28}{'정확도':>7}{'평균':>8}{'P50':>8}{'P95':>8}{'P99':>8}"
          f"{'출력tok':>8}{'추론tok':>8}{'형식오류':>6}")
    for x in r["rows"]:
        ot = (f"{x['out_tok']:8.1f}" if "out_tok" in x else " " * 8) + \
             (f"{x['reason_tok']:8.1f}" if "reason_tok" in x else " " * 8)
        print(f"{x['name']:28}{x['acc']:7.3f}{x['mean']:8.0f}{x['p50']:8.0f}"
              f"{x['p95']:8.0f}{x['p99']:8.0f}{ot}{x['fmt_err']:6d}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout-runs", type=int, default=3)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", default="benchmark_result.json")
    a = ap.parse_args()
    dev, hold = DEV[:a.limit], HOLDOUT[:a.limit]

    oa = OpenAI()
    with TypeSafeClient() as client:
        d = bench(dev, "개발셋", oa, client)
        show(d)
        th = d["threshold"]
        print(f"\n개발셋에서 고른 임계값 {th} 를 검증셋 {a.holdout_runs}회에 그대로 씁니다")
        hs = [bench(hold, f"검증셋 {i + 1}회", oa, client, threshold=th)
              for i in range(a.holdout_runs)]
        for h in hs:
            show(h)

    print(f"\n[검증셋 {len(hs)}회 평균]")
    for i, x in enumerate(hs[0]["rows"]):
        accs = [h["rows"][i]["acc"] for h in hs]
        print(f"  {x['name']:28} 정확도 {statistics.mean(accs):.3f} "
              f"({min(accs):.3f}~{max(accs):.3f})  "
              f"P50 {statistics.median(h['rows'][i]['p50'] for h in hs):6.0f} ms")
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"threshold_policy": "dev 1회에서 선택, 검증 전 회차에 고정",
                   "dev": d, "holdout": hs}, f, ensure_ascii=False, indent=2)
    print(f"\n저장: {a.out}")
