# -*- coding: utf-8 -*-
"""13-1: 답변 채점기. 두 단계로 나눈다.

한 번에 세 후보(정답·오답·무응답)로 물으면 "문서에 없습니다"라는 정직한
답변을 오답으로 분류한다. 채점기에게 에이전트가 실제로 본 문서가 아니라
정답 근거 문서를 주기 때문이다. 이 실수로 두 번 틀린 값을 냈다.
"""
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from langchain_typesafe import Choice, Noul

from corpus_tax import BY_ID, as_text

ANSWERED = Noul(
    instructions="이 답변은 질문에 대한 실질적인 답을 제공했는가?",
    criteria={"true": "질문이 물은 내용에 대해 구체적인 사실이나 수치, 절차를 알려줬다",
              "false": "자료가 없다, 확인할 수 없다는 취지로 답을 미뤘다"})

VERDICT = Choice(
    instructions="답변이 근거 문서에 비추어 맞는가?",
    criteria={"정답": "답변 내용이 근거 문서와 일치한다. 표현이 달라도 사실이 같으면 정답",
              "오답": "근거 문서와 다른 수치·조건을 말했거나 문서에 없는 내용을 단정했다"})

# 13-3 의 답변 검증용. 정답 근거 문서가 아니라 **에이전트가 실제로 본 문서**를 준다
VERIFY = {
    "grounded": Noul(
        instructions="답변에 담긴 사실이 검색된 문서에서 그대로 확인되는가?",
        criteria={"true": "답변의 수치와 조건이 문서에 적힌 것과 같다",
                  "false": "문서에 없는 수치나 조건을 말했거나 문서 내용을 뒤집거나 확장했다"}),
    "answerable": Noul(
        instructions="검색된 문서만으로 이 질문에 답할 수 있는가?",
        criteria={"true": "질문이 물은 내용이 문서 안에 직접 적혀 있다",
                  "false": "문서가 질문과 다른 주제이거나 질문이 물은 항목이 없다"}),
}
BLOCKED = "확인된 근거가 없어 답변을 보류했습니다. 담당자에게 문의해 주세요."


def grade(clf, row):
    """1단계는 답변만 보고 무응답인지 가른다. 답을 한 건에만 근거 문서를 준다."""
    p = clf.invoke({"state": {"질문": row["q"], "답변": row["answer"]},
                    "questions": {"answered": ANSWERED}}).nouls["answered"].noul
    if p < 0.5:
        return "무응답"
    key = "\n\n".join(as_text(BY_ID[r]) for r in row["refs"]) or "(근거 문서 없음)"
    return clf.invoke({
        "state": {"질문": row["q"], "근거 문서": key,
                  "채점 기준": row["memo"], "답변": row["answer"]},
        "questions": {"verdict": VERDICT}}).choices["verdict"].choice


def verify(clf, question, docs, answer, threshold=0.5):
    """에이전트가 실제로 본 문서를 놓고 묻는다."""
    body = "\n\n".join(as_text(BY_ID[i]) for i in docs) or "(검색된 문서 없음)"
    r = clf.invoke({"state": {"질문": question, "검색된 문서": body, "답변": answer},
                    "questions": VERIFY})
    sig = {k: r.nouls[k].noul for k in VERIFY}
    return sig, sig["grounded"] >= threshold
