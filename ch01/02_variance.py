# -*- coding: utf-8 -*-
"""01-2 실습: 확률을 얻으려면 얼마를 치러야 하는가.

애매한 문의를 N회 반복 호출해 분포를 추정하고 그 비용을 기록합니다.
Jev가 1회 호출로 돌려주는 것과 대조하기 위한 기준선입니다.
"""
import re
import sys
import time
from collections import Counter

sys.path.insert(0, ".")
from _common import LLM, require_llm

require_llm()
from openai import OpenAI

client = OpenAI()
Q = "쓰던 요금제가 저한테 안 맞는 것 같아요. 어떻게 하죠?"
N = 20

PROMPT = f"""다음 고객 문의를 담당 부서로 분류하세요.
billing, technical, sales, other 중 하나만 답하세요. 다른 말은 쓰지 마세요.

문의: {Q}"""


def main():
    print(f"문의: {Q}\n모델: {LLM}  반복: {N}회\n")
    answers, lat, tok_in, tok_out = [], [], 0, 0

    t_all = time.perf_counter()
    for _ in range(N):
        t0 = time.perf_counter()
        r = client.chat.completions.create(
            model=LLM, messages=[{"role": "user", "content": PROMPT}])
        lat.append((time.perf_counter() - t0) * 1000)
        tok_in += r.usage.prompt_tokens
        tok_out += r.usage.completion_tokens
        m = re.search(r"billing|technical|sales|other",
                      (r.choices[0].message.content or "").lower())
        answers.append(m.group(0) if m else "UNPARSED")
    total_ms = (time.perf_counter() - t_all) * 1000

    c = Counter(answers)
    print("추정 분포")
    for k, v in c.most_common():
        print(f"  {k:10} {v:3d}/{N}  {v/N:.2f}  {'#' * v}")
    print(f"\n합계 {total_ms/1000:.1f}초 (1회 평균 {sum(lat)/N:.0f}ms)")
    print(f"토큰 입력 {tok_in} / 출력 {tok_out}")
    print(f"확률 하나를 얻는 데 든 호출 수: {N}회")
    print("\nJev는 같은 정보를 1회 호출로 돌려줍니다. ch02/first_call.py 참고")


if __name__ == "__main__":
    main()
