# -*- coding: utf-8 -*-
"""13-1, 13-3: 에이전트 답변을 채점한다.

용어
    응답률    질문 중 실제로 답을 준 비율
    신뢰도    답한 것 중 맞은 비율          (11부와 같은 뜻)
    날조      문서에 근거가 없는데 답해버린 건

채점은 두 단계다. 한 번에 세 후보로 물으면 "문서에 없습니다"라는 정직한
무응답을 오답으로 분류한다. 원인은 채점기에게 에이전트가 실제로 본 문서가
아니라 정답 근거 문서를 주기 때문이다.

    python evaluate.py            Jev 검증 없음 (기준선)
    python evaluate.py --verify   Jev 로 답변 검증
"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from dotenv import load_dotenv

load_dotenv(HERE.parent / ".env")
os.environ.setdefault("OPENAI_API_BASE", os.environ.get("OPENAI_BASE_URL", ""))

from langchain_typesafe import TypeSafeClassifier

from agent_tax import MODEL as MODEL_NAME, ask, build
from judge_tax import BLOCKED, grade, verify
from dataset_tax import TAX_DEV, TAX_HOLDOUT

clf = TypeSafeClassifier()

# ---------- 실행 ----------
def run(dataset, label, app, use_verify):
    rows = []
    for question, group, refs, memo in dataset:
        answer, docs = ask(app, question)
        row = {"q": question, "group": group, "refs": refs, "memo": memo,
               "docs": docs, "answer": answer}
        if use_verify:
            sig, ok = verify(clf, question, docs, answer)
            row["signals"] = sig
            if not ok:
                row["answer"] = BLOCKED
                row["blocked"] = True
        row["grade"] = grade(clf, row)
        rows.append(row)

    ans = [r for r in rows if r["grade"] != "무응답"]
    ok = sum(1 for r in ans if r["grade"] == "정답")
    fab = sum(1 for r in ans if r["group"] == "B")
    print(f"\n[{label}]  n={len(rows)}")
    print(f"  {'군':>3} {'건수':>5} {'정답':>5} {'오답':>5} {'무응답':>6}")
    for g in "ABC":
        sel = [r for r in rows if r["group"] == g]
        c = {v: sum(1 for r in sel if r["grade"] == v) for v in ("정답", "오답", "무응답")}
        print(f"  {g:>3} {len(sel):5d} {c['정답']:5d} {c['오답']:5d} {c['무응답']:6d}")
    print(f"  응답률   {len(ans)}/{len(rows)} = {len(ans)/len(rows):.1%}")
    print(f"  신뢰도   {ok/len(ans):.1%}" if ans else "  신뢰도   -")
    print(f"  날조     {fab}건")
    return rows


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="13부 에이전트를 60건에 돌리고 채점한다")
    ap.add_argument("--prompt", choices=["fixed", "naive"], default="fixed",
                    help="fixed=13-2 한 줄 추가(기본), naive=13-1 첫 프롬프트")
    ap.add_argument("--verify", action="store_true", help="판단 모델로 답변을 검증한다")
    ap.add_argument("--limit", type=int, default=None, help="셋마다 앞 N건만 (점검용)")
    ap.add_argument("--out", default=None, help="저장 경로 (기본 results/result_<prompt>.json)")
    a = ap.parse_args()

    print("프롬프트:", a.prompt, "· 판단 검증:", "켬" if a.verify else "끔", "· 모델:", MODEL_NAME)
    app = build(prompt=a.prompt)
    dev, hold = TAX_DEV[:a.limit], TAX_HOLDOUT[:a.limit]
    out = {"meta": {"prompt": a.prompt, "verify": a.verify, "model": MODEL_NAME},
           "dev": run(dev, "개발셋", app, a.verify),
           "holdout": run(hold, "검증셋", app, a.verify)}
    path = Path(a.out) if a.out else HERE / "results" / (
        f"result_{a.prompt}{'_verify' if a.verify else ''}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n저장: {path}")
