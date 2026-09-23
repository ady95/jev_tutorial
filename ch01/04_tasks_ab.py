# -*- coding: utf-8 -*-
"""01-3 / 06-3: 과제 A(분류)와 과제 B(다단계 산술)를 여러 모델에 준다.

책의 01-3 과 06-3 표가 이 과제로 잰 것입니다. 과제당 3건입니다.
.env 의 OPENAI_MODEL_SMALL / OPENAI_MODEL / OPENAI_MODEL_FRONTIER 를 씁니다.
책은 gpt-6-astra, gpt-5.6-sol, gpt-5.6-terra, gpt-5.6-luna, gpt-6-luna 다섯을 비교했습니다.
비교할 모델을 MODELS 리스트에 직접 적어도 됩니다.

과제 B 는 각 단계가 정수로 떨어지는지 assert 로 확인합니다. 처음 낸 문제 하나의
답이 72.5 로 나와 모든 모델이 틀린 것처럼 보였던 일이 있었습니다.
"""
import re
import statistics
import sys
import time

sys.path.insert(0, ".")
from _common import LLM, LLM_FRONTIER, LLM_SMALL, require_llm
from dataset.inquiries import INQUIRIES

require_llm()
from openai import OpenAI

client = OpenAI()
MODELS = list(dict.fromkeys([LLM_SMALL, LLM, LLM_FRONTIER]))

A_PROMPT = ("다음 고객 문의를 billing, technical, sales, other 중 하나로 분류하세요. "
            "부서 이름 하나만 답하세요.\n\n문의: ")
A_CASES = [(x, y) for x, y, _ in INQUIRIES[:3]]

B_PROMPT = """창고 재고를 계산하세요. 마지막 줄에 최종 수량만 숫자로 쓰세요.

월요일 아침 재고는 {a}개입니다.
화요일에 {b}개가 입고됐습니다.
수요일에 남은 재고의 {c}분의 1이 출고됐습니다.
목요일에 {d}개가 반품으로 들어왔습니다.
금요일에 남은 재고의 절반이 출고됐습니다.

금요일 출고 후 재고는 몇 개입니까?"""


def b_case(a, b, c, d):
    """문제와 정답을 만든다. 나누어떨어지지 않으면 문제를 잘못 낸 것이다."""
    v = a + b
    assert v % c == 0, f"{v} 가 {c} 로 안 나눠떨어짐"
    v -= v // c
    v += d
    assert v % 2 == 0, f"{v} 가 홀수라 절반이 정수가 아님"
    return B_PROMPT.format(a=a, b=b, c=c, d=d), v // 2


B_CASES = [b_case(120, 60, 3, 24), b_case(200, 40, 4, 10), b_case(90, 30, 2, 14)]


def call(model, content):
    t0 = time.perf_counter()
    r = client.chat.completions.create(model=model,
                                       messages=[{"role": "user", "content": content}])
    return (time.perf_counter() - t0) * 1000, r


def measure(model):
    call(model, A_PROMPT + "워밍업")                    # 첫 호출 제외

    la, oka = [], 0
    for text, truth in A_CASES:
        ms, r = call(model, A_PROMPT + text)
        la.append(ms)
        oka += (r.choices[0].message.content or "").strip().rstrip(".").lower() == truth

    lb, okb, tb, got = [], 0, [], []
    for prompt, answer in B_CASES:
        ms, r = call(model, prompt)
        lb.append(ms)
        tb.append(r.usage.completion_tokens)
        nums = re.findall(r"-?\d+", (r.choices[0].message.content or "").replace(",", ""))
        v = int(nums[-1]) if nums else None             # 마지막 숫자를 답으로 본다
        got.append(v)
        okb += v == answer

    return {"A": (oka, statistics.mean(la)),
            "B": (okb, statistics.mean(lb), statistics.mean(tb), got)}


def main():
    print("과제 B 정답:", [ans for _, ans in B_CASES])
    print(f"\n{'모델':16}{'A정답':>7}{'A지연':>10}{'B정답':>7}{'B지연':>10}{'B출력tok':>10}")
    for m in MODELS:
        r = measure(m)
        oka, ma = r["A"]
        okb, mb, tok, got = r["B"]
        print(f"{m:16}{oka:4}/{len(A_CASES)}{ma:8.0f}ms{okb:4}/{len(B_CASES)}"
              f"{mb:8.0f}ms{tok:10.0f}")
        if okb < len(B_CASES):
            print(f"  B 응답값: {got}")


if __name__ == "__main__":
    main()
