# -*- coding: utf-8 -*-
"""13-1 ~ 13-5 실습: 에이전트를 끝까지 돌리고 채점합니다.

    python ch13/run_eval.py              기준선 (낱말 겹침)
    python ch13/run_eval.py --char       문자 3-gram 검색
    python ch13/run_eval.py --char --gate  검색 개선 + 답변 게이트

채점기는 **두 단계**입니다. 한 번에 세 후보로 물었더니 기권을 오답으로
분류하는 사고가 났습니다. 원인은 채점기에게 **에이전트가 실제로 본 문서가
아니라 정답 근거 문서**를 함께 준 것이었습니다. 그러면 "제공된 문서에
없습니다"라는 정직한 기권이 거짓말로 보입니다.

LLM과 Jev를 모두 부르므로 60건에 수 분이 걸립니다.
"""
import json
import sys

sys.path.insert(0, ".")
from _common import require_jev, require_llm, warmup_jev

require_jev()
require_llm()
from typesafe_sdk import Choice, Noul, TypeSafeClient

import ch13.agent_tax as agent_tax
from ch13.corpus_tax import BY_ID, as_text
from ch13.dataset_tax import TAX_DEV, TAX_HOLDOUT
from ch13.retrievers import retrieve_char

# ---------- 채점기 ----------
ANSWERED = Noul(
    instructions="이 답변은 질문에 대한 실질적인 답을 제공했는가?",
    criteria={"true": "질문이 물은 내용에 대해 구체적인 사실이나 수치, 절차를 알려줬다",
              "false": "자료가 없다, 확인할 수 없다, 담당자에게 문의하라는 취지로 답을 미뤘다"})

VERDICT = Choice(
    instructions="답변이 근거 문서에 비추어 맞는가?",
    criteria={"정답": "답변 내용이 근거 문서와 일치한다. 표현이 달라도 사실이 같으면 정답이다",
              "오답": "근거 문서와 다른 수치·조건·대상을 말했거나, 문서에 없는 내용을 "
                      "단정해 말했거나, 질문이 물은 것과 다른 것을 답했다"})


def judge(client, row):
    p = client.system_one(
        state={"질문": row["q"], "답변": row["answer"]},
        questions={"answered": ANSWERED},
    ).nouls["answered"].noul
    if p < 0.5:
        return "기권"
    key = "\n\n".join(as_text(BY_ID[r]) for r in row["refs"]) or "(근거 문서 없음)"
    return client.system_one(
        state={"질문": row["q"], "근거 문서": key,
               "채점 기준": row["memo"], "답변": row["answer"]},
        questions={"verdict": VERDICT},
    ).choices["verdict"].choice


# ---------- 답변 게이트 ----------
SIGNALS = {
    "answerable": Noul(
        instructions="아래 문서만으로 이 질문에 답할 수 있는가?",
        criteria={"true": "질문이 물은 내용이 문서 안에 직접 적혀 있다",
                  "false": "문서가 질문과 다른 주제이거나, 질문이 물은 항목은 적혀 있지 않다"}),
    "grounded": Noul(
        instructions="답변에 담긴 사실이 문서에서 그대로 확인되는가?",
        criteria={"true": "답변의 수치와 조건이 문서에 적힌 것과 같다",
                  "false": "문서에 없는 수치나 조건을 말했거나, 문서 내용을 뒤집거나 확장해 말했다"}),
}

ALWAYS_REVIEW = ("절세", "가산세", "계약", "소명", "조사")


def gate_signals(client, row):
    """에이전트가 실제로 본 문서를 놓고 묻습니다. 정답 근거 문서가 아닙니다."""
    body = "\n\n".join(as_text(BY_ID[i]) for i in row["docs"]) or "(검색된 문서 없음)"
    r = client.system_one(
        state={"질문": row["q"], "검색된 문서": body, "답변": row["answer"]},
        questions=SIGNALS)
    return {k: r.nouls[k].noul for k in SIGNALS}


def should_answer(question, signals, threshold=0.5, use_policy=False):
    """기본값은 답하지 않는 것. 근거가 확인되면 답합니다.

    use_policy 를 켜면 위험 영역(13-5)까지 걸러냅니다. 13-4의 측정은
    게이트만 적용한 것이라 기본값은 꺼둡니다.
    """
    if use_policy and any(k in question for k in ALWAYS_REVIEW):
        return False
    return signals["grounded"] >= threshold


# ---------- 실행 ----------
def run(dataset, label, app, client, use_gate, use_policy=False):
    rows = []
    for question, group, refs, memo in dataset:
        out = app.invoke({"question": question, "docs": [], "answer": ""})
        row = {"q": question, "group": group, "refs": refs, "memo": memo,
               "docs": [d[0] for d in out["docs"]], "answer": out["answer"]}
        row["verdict"] = judge(client, row)
        if use_gate and row["verdict"] != "기권":
            sig = gate_signals(client, row)
            row["gate"] = sig
            if not should_answer(question, sig, use_policy=use_policy):
                row["verdict"] = "기권"          # 게이트가 막았다
        rows.append(row)

    by = {g: [r for r in rows if r["group"] == g] for g in "ABC"}
    ans = [r for r in rows if r["verdict"] != "기권"]
    ok = sum(1 for r in ans if r["verdict"] == "정답")
    fab = sum(1 for r in ans if r["group"] == "B")
    print(f"\n[{label}]  n={len(rows)}")
    print(f"  {'군':>3} {'건수':>5} {'정답':>5} {'오답':>5} {'기권':>5}")
    for g in "ABC":
        c = {v: sum(1 for r in by[g] if r["verdict"] == v) for v in ("정답", "오답", "기권")}
        print(f"  {g:>3} {len(by[g]):5d} {c['정답']:5d} {c['오답']:5d} {c['기권']:5d}")
    print(f"  coverage            {len(ans)}/{len(rows)} = {len(ans)/len(rows):.1%}")
    print(f"  selective accuracy  {ok/len(ans):.1%}" if ans else "  selective accuracy  -")
    print(f"  날조 (B군에서 답함)  {fab}건")
    return rows


if __name__ == "__main__":
    if "--char" in sys.argv:
        agent_tax.RETRIEVER = lambda q: [BY_ID[i] for i in retrieve_char(q, k=3)]
        print("검색기: 문자 3-gram")
    else:
        print("검색기: 낱말 겹침 (기준선)")
    use_gate = "--gate" in sys.argv
    use_policy = "--policy" in sys.argv
    print("답변 게이트:", "켬" if use_gate else "끔")
    print("위험 영역 정책:", "켬" if use_policy else "끔")

    app = agent_tax.build_graph()
    with TypeSafeClient() as client:
        warmup_jev(client, ANSWERED)
        out = {"dev": run(TAX_DEV, "개발셋", app, client, use_gate, use_policy),
               "holdout": run(TAX_HOLDOUT, "검증셋", app, client, use_gate, use_policy)}

    name = f"ch13_result_{'char' if '--char' in sys.argv else 'word'}" \
           f"{'_gate' if use_gate else ''}{'_policy' if use_policy else ''}.json"
    with open(name, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n저장: {name}")
