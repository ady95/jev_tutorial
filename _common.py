# -*- coding: utf-8 -*-
"""예제 공통 유틸. 저장소 루트에서 실행하는 것을 전제로 합니다."""
import os
import sys

from dotenv import load_dotenv

load_dotenv()

# Windows 콘솔에서 한글이 깨지지 않도록
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LLM = os.getenv("OPENAI_MODEL", "gpt-6-luna")
LLM_SMALL = os.getenv("OPENAI_MODEL_SMALL", LLM)
LLM_FRONTIER = os.getenv("OPENAI_MODEL_FRONTIER", LLM)


def require_jev():
    if not os.getenv("TYPESAFE_API_KEY"):
        sys.exit("TYPESAFE_API_KEY 가 없습니다. .env 를 확인하세요.")


def require_llm():
    if not os.getenv("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY 가 없습니다. 이 예제는 LLM 비교가 필요합니다.")


def pct(values, p):
    """백분위. 라이브러리 없이 계산합니다."""
    xs = sorted(values)
    i = min(len(xs) - 1, int(round((p / 100) * (len(xs) - 1))))
    return xs[i]


def warmup_jev(client, question):
    """첫 호출은 연결 비용 때문에 느립니다. 측정 전에 한 번 버립니다."""
    client.system_one(state="워밍업", questions={"_": question})
