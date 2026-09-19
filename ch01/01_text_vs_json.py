# -*- coding: utf-8 -*-
"""01-1 실습: 같은 분류 문제를 자연어 / JSON 두 방식으로 요청해 비교.

측정: 형식 준수 여부, 파싱 가능 여부, 지연시간, 토큰 사용량
TypeSafe 키 없이 실행할 수 있습니다 (LLM 키만 필요).
"""
import json
import re
import sys
import time

sys.path.insert(0, ".")
from _common import LLM, require_llm
from dataset.inquiries import TEXTS

require_llm()
from openai import OpenAI

client = OpenAI()
N = 10

PROMPT_TEXT = """다음 고객 문의를 분석해주세요.

문의: {q}

어느 부서로 보내야 하는지(billing/technical/sales/other), 고객이 얼마나 화가 났는지(0~3),
환불을 요구하는지 알려주세요."""

PROMPT_JSON = """다음 고객 문의를 분석해서 JSON으로만 답하세요. 다른 말은 하지 마세요.

문의: {q}

형식:
{{"department": "billing|technical|sales|other", "anger": 0~3의 정수, "refund": true 또는 false}}"""


def call(prompt):
    t0 = time.perf_counter()
    r = client.chat.completions.create(model=LLM, messages=[{"role": "user", "content": prompt}])
    ms = (time.perf_counter() - t0) * 1000
    return r.choices[0].message.content or "", ms, r.usage.completion_tokens


def try_parse(text):
    """모델이 돌려준 문자열에서 JSON을 꺼내 본다. 실무에서 흔히 쓰는 방어 코드."""
    try:
        return json.loads(text), "직접 파싱"
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.S)
    if m:
        try:
            return json.loads(m.group(1)), "코드펜스 제거 후"
        except json.JSONDecodeError:
            pass
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            return json.loads(m.group(0)), "중괄호 추출 후"
        except json.JSONDecodeError:
            pass
    return None, "파싱 실패"


def main():
    print(f"model={LLM}  n={N}\n")
    rows = []
    for i, q in enumerate(TEXTS[:N], 1):
        text, ms1, tok1 = call(PROMPT_TEXT.format(q=q))
        js, ms2, tok2 = call(PROMPT_JSON.format(q=q))
        parsed, how = try_parse(js)
        ok = "OK" if parsed else "실패"
        print(f"[{i:2d}] 자연어 {ms1:6.0f}ms/{tok1:4d}tok   "
              f"JSON {ms2:6.0f}ms/{tok2:4d}tok  파싱 {ok} ({how})")
        rows.append({"text_ms": ms1, "text_tok": tok1, "json_ms": ms2,
                     "json_tok": tok2, "parsed": parsed, "how": how})

    n = len(rows)
    ok = sum(1 for r in rows if r["parsed"])
    direct = sum(1 for r in rows if r["how"] == "직접 파싱")
    print(f"\n파싱 성공 {ok}/{n}   그중 추가 가공 없이 {direct}/{n}")
    print(f"자연어 평균 {sum(r['text_ms'] for r in rows)/n:.0f}ms, "
          f"출력 {sum(r['text_tok'] for r in rows)/n:.0f}tok")
    print(f"JSON   평균 {sum(r['json_ms'] for r in rows)/n:.0f}ms, "
          f"출력 {sum(r['json_tok'] for r in rows)/n:.0f}tok")
    print("\n책의 결과: 10/10 파싱 성공. 형식은 문제가 아니었습니다.")


if __name__ == "__main__":
    main()
