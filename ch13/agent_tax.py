# -*- coding: utf-8 -*-
"""13-1 실습: LangGraph 세무 상담 에이전트 (판단 계층 없는 기준선).

Jev를 넣기 전에 무엇이 어떻게 틀리는지 먼저 잽니다. 기준선 없이 개선을
주장할 수 없다는 것이 9부의 교훈입니다.

    START -> retrieve -> generate -> END

검색은 가상 문서에 대한 낱말 겹침입니다. **한국어 조사 때문에 무너집니다.**
일부러 나쁘게 만든 것이 아니라 교과서적인 출발점이고, 13-2에서 그 실패를
진단합니다.

    pip install langgraph
"""
import sys
import re
from typing import TypedDict

sys.path.insert(0, ".")
from _common import LLM, require_llm

require_llm()
from langgraph.graph import END, START, StateGraph
from openai import OpenAI

from ch13.corpus_tax import CORPUS, as_text

TOP_K = 3
SYSTEM = (
    "당신은 한빛소프트웨어 세무 안내 담당자입니다. "
    "아래 사내 안내 문서만 근거로 삼아 질문에 답하세요. "
    "답변은 세 문장 이내로 간결하게 쓰세요."
)


class S(TypedDict):
    question: str
    docs: list
    answer: str


def _tokens(text):
    return set(re.findall(r"[가-힣A-Za-z0-9]{2,}", text))


def retrieve_docs(question, k=TOP_K):
    """낱말 겹침 검색. 조사가 붙으면 매칭이 실패합니다."""
    q = _tokens(question)
    scored = []
    for doc in CORPUS:
        overlap = len(q & _tokens(f"{doc[2]} {doc[3]}"))
        if overlap:
            scored.append((overlap / (len(q) ** 0.5 + 1), doc))
    scored.sort(key=lambda x: -x[0])
    return [d for _, d in scored[:k]]


# 검색기를 갈아 끼울 수 있게 모듈 변수로 둡니다. 13-3에서 이것만 바꿉니다.
RETRIEVER = retrieve_docs


def node_retrieve(state: S) -> S:
    return {"docs": RETRIEVER(state["question"])}


def node_generate(state: S) -> S:
    context = "\n\n".join(as_text(d) for d in state["docs"]) or "(검색된 문서 없음)"
    r = OpenAI().chat.completions.create(
        model=LLM,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user",
             "content": f"[사내 안내 문서]\n{context}\n\n[질문]\n{state['question']}"},
        ],
    )
    return {"answer": r.choices[0].message.content.strip()}


def build_graph():
    g = StateGraph(S)
    g.add_node("retrieve", node_retrieve)
    g.add_node("generate", node_generate)
    g.add_edge(START, "retrieve")
    g.add_edge("retrieve", "generate")
    g.add_edge("generate", END)
    return g.compile()


if __name__ == "__main__":
    app = build_graph()
    for q in ("일반과세자 부가세 신고는 언제까지 하나요?",   # 문서에 있다
              "상속세 세율이 어떻게 되나요?"):              # 문서에 없다
        out = app.invoke({"question": q, "docs": [], "answer": ""})
        print(f"\nQ  {q}")
        print(f"검색 {[d[0] for d in out['docs']]}")
        print(f"A  {out['answer']}")
