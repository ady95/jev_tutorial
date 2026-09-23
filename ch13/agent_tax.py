# -*- coding: utf-8 -*-
"""13-1: LangChain 세무 상담 에이전트.

langchain.agents.create_agent 로 만듭니다. 도구는 넷입니다.

    search_tax_docs     사내 안내 문서 검색        안전
    create_ticket       담당자에게 검토 요청        안전
    email_customer      고객에게 메일 발송          위험 (외부 전송)
    update_filing       신고 기록 변경             위험 (되돌릴 수 없음)

뒤의 두 개가 13-4에서 harness 가 막을 대상입니다.
"""
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from langchain.agents import create_agent
from langchain_core.tools import tool

from corpus_tax import CORPUS, as_text

MODEL = os.getenv("TAX_AGENT_MODEL", "openai:gpt-6-luna")
TOP_K = 3

# 13-1 의 첫 프롬프트. 날조가 나온 조건이며 13-4 측정의 입력 답변을 만든다
SYSTEM_NAIVE = (
    "당신은 한빛소프트웨어 세무 안내 담당자입니다. "
    "search_tax_docs 로 문서를 찾아 고객 질문에 친절하게 답하세요. "
    "답변은 세 문장 이내로 간결하게 쓰세요."
)

# 13-2 에서 고친 프롬프트. 기본값이다
SYSTEM = (
    "당신은 한빛소프트웨어 세무 안내 담당자입니다. "
    "반드시 search_tax_docs 로 사내 안내 문서를 찾은 뒤, "
    "그 문서에 적힌 내용만 근거로 답하세요. "
    "문서에 없는 내용은 지어내지 말고 없다고 답하세요. "
    "답변은 세 문장 이내로 간결하게 쓰세요."
)

# 도구가 무엇을 했는지 밖에서 확인하려고 기록해둡니다
CALLS = []


def _ngrams(text, n=3):
    text = re.sub(r"\s+", "", text)
    return {text[i:i + n] for i in range(len(text) - n + 1)}


DOC_NG = {d[0]: _ngrams(f"{d[1]} {d[2]} {d[3]}") for d in CORPUS}
BY_ID = {d[0]: d for d in CORPUS}


def retrieve(question, k=TOP_K, floor=0.02):
    """문자 3-gram 검색. 한국어 조사 때문에 낱말 단위로는 매칭이 깨집니다."""
    qg = _ngrams(question)
    if not qg:
        return []
    scored = [(len(qg & DOC_NG[i]) / len(qg), i) for i in DOC_NG]
    scored = [(s, i) for s, i in scored if s >= floor]
    scored.sort(reverse=True)
    return [i for _, i in scored[:k]]


@tool
def search_tax_docs(query: str) -> str:
    """사내 세무 안내 문서를 검색한다. 질문과 관련된 문서를 최대 3건 돌려준다."""
    ids = retrieve(query)
    CALLS.append(("search_tax_docs", query, ids))
    if not ids:
        return "검색 결과 없음"
    return "\n\n".join(as_text(BY_ID[i]) for i in ids)


@tool
def create_ticket(summary: str) -> str:
    """담당자에게 검토 요청 티켓을 만든다."""
    CALLS.append(("create_ticket", summary, None))
    return f"티켓 생성됨: {summary[:40]}"


@tool
def email_customer(address: str, body: str) -> str:
    """고객에게 메일을 보낸다. 외부로 나가며 되돌릴 수 없다."""
    CALLS.append(("email_customer", address, body[:60]))
    return f"메일 발송됨: {address}"


@tool
def update_filing(record_id: str, field: str, value: str) -> str:
    """신고 기록을 변경한다. 되돌릴 수 없다."""
    CALLS.append(("update_filing", record_id, f"{field}={value}"))
    return f"기록 변경됨: {record_id}"


SAFE_TOOLS = [search_tax_docs, create_ticket]
RISKY_TOOLS = [email_customer, update_filing]
ALL_TOOLS = SAFE_TOOLS + RISKY_TOOLS


def build(middleware=None, tools=None, prompt="fixed"):
    """prompt: "fixed"(13-2, 기본) 또는 "naive"(13-1)."""
    system = SYSTEM_NAIVE if prompt == "naive" else SYSTEM
    return create_agent(
        MODEL,
        tools=tools if tools is not None else SAFE_TOOLS,
        system_prompt=system,
        middleware=middleware or [],
    )


def ask(app, question):
    """질문 하나를 던지고 (최종 답변, 검색된 문서 id) 를 돌려줍니다."""
    CALLS.clear()
    out = app.invoke({"messages": [{"role": "user", "content": question}]})
    answer = out["messages"][-1].content
    docs = []
    for name, _arg, ids in CALLS:
        if name == "search_tax_docs" and ids:
            docs.extend(ids)
    return answer, list(dict.fromkeys(docs))


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(HERE.parent / ".env")
    app = build()
    for q in ("일반과세자 부가세 신고는 언제까지 하나요?",
              "상속세 세율이 어떻게 되나요?"):
        a, d = ask(app, q)
        print(f"\nQ  {q}")
        print(f"검색 {d}")
        print(f"A  {a}")
