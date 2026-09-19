# -*- coding: utf-8 -*-
"""01-1 보강: JSON 형식 준수율을 여러 모델에 걸쳐 측정.

.env 의 OPENAI_MODEL_SMALL / OPENAI_MODEL / OPENAI_MODEL_FRONTIER 를 씁니다.
비교할 모델을 MODELS 리스트에 직접 적어도 됩니다.
"""
import json
import re
import sys
import time

sys.path.insert(0, ".")
from _common import LLM, LLM_FRONTIER, LLM_SMALL, require_llm
from dataset.inquiries import TEXTS

require_llm()
from openai import OpenAI

client = OpenAI()
MODELS = list(dict.fromkeys([LLM_SMALL, LLM, LLM_FRONTIER]))
N = 10

PROMPT = """다음 고객 문의를 분석해서 JSON으로만 답하세요. 다른 말은 하지 마세요.

문의: {q}

형식:
{{"department": "billing|technical|sales|other", "anger": 0~3의 정수, "refund": true 또는 false}}"""

WANT = {"department", "anger", "refund"}
VALID_DEPT = {"billing", "technical", "sales", "other"}


def parse(text):
    try:
        return json.loads(text), "직접"
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.S)
    if m:
        try:
            return json.loads(m.group(1)), "코드펜스제거"
        except json.JSONDecodeError:
            pass
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            return json.loads(m.group(0)), "중괄호추출"
        except json.JSONDecodeError:
            pass
    return None, "실패"


def main():
    print(f"{'모델':22} {'바로파싱':>9} {'가공후':>7} {'실패':>5} "
          f"{'키일치':>7} {'값유효':>7} {'평균ms':>8} {'출력tok':>8}")
    for m in MODELS:
        direct = extra = fail = keyok = valok = 0
        lats, toks = [], []
        for q in TEXTS[:N]:
            try:
                t0 = time.perf_counter()
                r = client.chat.completions.create(
                    model=m, messages=[{"role": "user", "content": PROMPT.format(q=q)}])
                lats.append((time.perf_counter() - t0) * 1000)
                toks.append(r.usage.completion_tokens)
                txt = r.choices[0].message.content or ""
            except Exception as e:
                fail += 1
                print(f"  {m} 호출 실패: {str(e)[:60]}")
                continue
            parsed, how = parse(txt)
            if how == "직접":
                direct += 1
            elif how == "실패":
                fail += 1
            else:
                extra += 1
            if parsed:
                if set(parsed.keys()) == WANT:
                    keyok += 1
                d = parsed.get("department")
                a = parsed.get("anger")
                rf = parsed.get("refund")
                if (d in VALID_DEPT and isinstance(a, int)
                        and 0 <= a <= 3 and isinstance(rf, bool)):
                    valok += 1
        avg_ms = sum(lats) / len(lats) if lats else 0
        avg_tok = sum(toks) / len(toks) if toks else 0
        print(f"{m:22} {direct:6d}/{N} {extra:5d}/{N} {fail:3d}/{N} "
              f"{keyok:5d}/{N} {valok:5d}/{N} {avg_ms:8.0f} {avg_tok:8.1f}")

    print("\n책의 결과: 모델 5종 x 10건 = 50회 전부 통과.")
    print("남은 차이는 출력 토큰(17 vs 55, 3배) — 형식이 아니라 비용의 문제입니다.")


if __name__ == "__main__":
    main()
