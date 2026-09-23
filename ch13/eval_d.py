# -*- coding: utf-8 -*-
"""D군 실험 — 조건이 부족한 질문에 되묻는가.

세 조건을 비교한다.

    base    지금 프롬프트 ("문서에 없으면 지어내지 마라")
    prompt  + "조건이 필요하면 되물어라" 지시를 프롬프트에 추가
    jev     base 프롬프트 + Jev 가 질문 단계에서 조건 부족을 판정

A군을 대조로 함께 잰다. **무조건 되묻는 시스템은 D군 만점이지만 쓸모가 없다.**

    python eval_d.py base
    python eval_d.py prompt
    python eval_d.py jev
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

from langchain_typesafe import Noul, TypeSafeClassifier

import agent_tax as A
from dataset_d import D_DEV, D_HOLDOUT
from dataset_tax import TAX_DEV, TAX_HOLDOUT

clf = TypeSafeClassifier()

BASE_PROMPT = A.SYSTEM
ASK_BACK_PROMPT = BASE_PROMPT + (
    " 답이 소득·업종·사업자 유형 같은 조건에 따라 달라지는데 질문에 그 조건이 "
    "없으면, 조건을 가정해 답하지 말고 사용자에게 되물으세요."
)

# Jev — 답변이 아니라 **질문**을 본다. 사후 검증이 아니라 사전 분류다.
NEEDS_INFO = Noul(
    instructions="이 질문에 답하려면 사용자에게 조건을 더 물어봐야 하는가?",
    criteria={
        "true": "답이 소득금액·업종·사업자 유형·연도 같은 조건에 따라 갈리는데 "
                "질문에 그 조건이 없다",
        "false": "질문에 담긴 정보만으로 답이 하나로 정해지거나, "
                 "조건과 무관한 일반적인 사실을 묻고 있다",
    },
)

# 답변이 되물었는지 판정
ASKED_BACK = Noul(
    instructions="이 답변은 사용자에게 추가 정보를 요청했는가?",
    criteria={"true": "답을 주기 전에 사용자의 상황이나 조건을 되물었다",
              "false": "되묻지 않고 답을 줬거나, 자료가 없다고만 했다"},
)

ASK_TEMPLATE = "답변 전에 확인이 필요합니다. {missing}를 알려주시겠습니까?"


def needs_more_info(question, threshold=0.5):
    p = clf.invoke({"state": {"질문": question},
                    "questions": {"need": NEEDS_INFO}}).nouls["need"].noul
    return p, p >= threshold


def asked_back(question, answer):
    return clf.invoke({
        "state": {"질문": question, "답변": answer},
        "questions": {"asked": ASKED_BACK}}).nouls["asked"].noul >= 0.5


def run(mode, label, d_set, a_set):
    A.SYSTEM = ASK_BACK_PROMPT if mode == "prompt" else BASE_PROMPT
    app = A.build()

    rows = []
    for question, refs, missing in [(q, r, m) for q, r, m in d_set]:
        rows.append(handle(app, mode, question, "D"))
    for question, group, refs, memo in a_set:
        if group != "A":
            continue
        rows.append(handle(app, mode, question, "A"))

    d = [r for r in rows if r["group"] == "D"]
    a = [r for r in rows if r["group"] == "A"]
    dr = sum(r["asked"] for r in d) / len(d)
    ar = sum(r["asked"] for r in a) / len(a)
    print(f"  {label:26} D군 되묻기 {dr:6.1%} ({sum(r['asked'] for r in d)}/{len(d)})"
          f"   A군 과잉 되묻기 {ar:6.1%} ({sum(r['asked'] for r in a)}/{len(a)})")
    return rows


def handle(app, mode, question, group):
    row = {"q": question, "group": group, "mode": mode}
    if mode == "jev":
        p, need = needs_more_info(question)
        row["p_need"] = p
        if need:
            row["answer"] = "답변 전에 확인이 필요합니다. 관련 조건을 알려주시겠습니까?"
            row["asked"] = True
            return row
    answer, docs = A.ask(app, question)
    row["answer"] = answer
    row["docs"] = docs
    row["asked"] = asked_back(question, answer)
    return row


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "base"
    names = {"base": "지금 프롬프트", "prompt": "되묻기 지시 추가", "jev": "Jev 사전 분류"}
    print(f"조건: {names[mode]}")
    out = {"dev": run(mode, "개발셋", D_DEV, TAX_DEV),
           "holdout": run(mode, "검증셋", D_HOLDOUT, TAX_HOLDOUT)}
    (HERE / f"d_{mode}.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장: d_{mode}.json")
