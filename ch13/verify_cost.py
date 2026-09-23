# -*- coding: utf-8 -*-
"""13-4 측정 도구 — 판단 1개와 5개를 판단 모델과 LLM 으로 잰다.

입력은 evaluate.py --prompt naive 가 만든 답변 캐시다. 에이전트는 다시
돌리지 않는다.

    python ch13/evaluate.py --prompt naive
    python ch13/verify_cost.py --split dev     --out ch13/results/cost_dev.json
    python ch13/verify_cost.py --split holdout --out ch13/results/cost_holdout.json
    python ch13/aggregate13.py ch13/results/cost_dev.json ch13/results/cost_holdout.json

네 종류 호출의 순서를 건마다 섞는다. 안 섞으면 먼저 나가는 호출이 연결
비용을 더 물어, 판단 1개가 5개보다 느리게 나오는 착시가 생긴다.

품질 비교는 판단 하나(grounded)만 한다. 다섯 개를 물은 쪽은 원응답을
저장하지만 항목별 정답 기준이 없어 채점하지 않는다.
"""
import argparse
import json
import os
import random
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from dotenv import load_dotenv

load_dotenv(HERE.parent / ".env")
os.environ.setdefault("OPENAI_API_BASE", os.environ.get("OPENAI_BASE_URL", ""))

from langchain_typesafe import Noul, TypeSafeClassifier
from openai import OpenAI

from agent_tax import BY_ID
from corpus_tax import as_text

clf = TypeSafeClassifier()
oa = OpenAI()
LLM = os.getenv("TAX_AGENT_MODEL", "gpt-6-luna").replace("openai:", "")

QUESTIONS = {
    "grounded": Noul(
        instructions="답변에 담긴 사실이 검색된 문서에서 그대로 확인되는가?",
        criteria={"true": "답변의 수치와 조건이 문서에 적힌 것과 같다",
                  "false": "문서에 없는 수치나 조건을 말했거나 문서 내용을 뒤집었다"}),
    "complete": Noul(
        instructions="질문이 물은 것에 빠짐없이 답했는가?",
        criteria={"true": "질문의 모든 항목에 답했다", "false": "일부를 빠뜨렸다"}),
    "conditioned": Noul(
        instructions="답이 조건에 따라 갈리는 경우 그 조건을 밝혔는가?",
        criteria={"true": "적용 조건을 함께 적었거나 조건이 필요 없다",
                  "false": "조건을 밝히지 않고 하나로 단정했다"}),
    "not_overclaiming": Noul(
        instructions="문서가 말하지 않은 것까지 단정하지 않았는가?",
        criteria={"true": "문서 범위 안에서만 말했다", "false": "추론을 사실처럼 단정했다"}),
    "needs_followup": Noul(
        instructions="사용자에게 추가로 물어봐야 하는가?",
        criteria={"true": "조건이 빠져 답을 정할 수 없다", "false": "그대로 답할 수 있다"}),
}
ONE = {"grounded": QUESTIONS["grounded"]}

PROMPT_ONE = """다음 답변이 검색된 문서에 근거하는지 판정하세요.

[검색된 문서]
{docs}

[질문]
{q}

[답변]
{a}

문서의 수치·조건과 답변이 일치하면 yes, 문서에 없는 것을 말했거나 뒤집었으면 no.
yes 또는 no 한 단어로만 답하세요."""

PROMPT_FIVE = """다음 답변을 다섯 항목으로 판정하세요.

[검색된 문서]
{docs}

[질문]
{q}

[답변]
{a}

각 항목에 yes 또는 no 로만 답하고 JSON 한 줄로 출력하세요.
grounded: 답변의 사실이 문서에서 확인되는가
complete: 질문이 물은 것에 빠짐없이 답했는가
conditioned: 조건에 따라 갈리는 경우 조건을 밝혔는가
not_overclaiming: 문서가 말하지 않은 것을 단정하지 않았는가
needs_followup: 사용자에게 추가로 물어봐야 하는가"""


def llm_call(prompt):
    """(지연 ms, 입력 토큰, 출력 토큰, 그중 추론 토큰, 본문)"""
    t0 = time.perf_counter()
    r = oa.chat.completions.create(model=LLM, messages=[{"role": "user", "content": prompt}])
    ms = (time.perf_counter() - t0) * 1000
    u = r.usage
    d = getattr(u, "completion_tokens_details", None)
    d = (d if isinstance(d, dict) else d.model_dump()) if d else {}
    return (ms, u.prompt_tokens, u.completion_tokens, d.get("reasoning_tokens", 0) or 0,
            (r.choices[0].message.content or "").strip())


def jev_call(state, questions):
    """(지연 ms, 입력 토큰, 출력 토큰, 응답)"""
    t0 = time.perf_counter()
    r = clf.invoke({"state": state, "questions": questions})
    ms = (time.perf_counter() - t0) * 1000
    return ms, r.usage.input_tokens, r.usage.output_tokens, r


def measure(sample, seed=11):
    """sample 의 각 답변에 네 종류 호출을 무작위 순서로 보낸다."""
    rng = random.Random(seed)
    jev_call({"질문": "워밍업", "답변": "워밍업"}, ONE)          # 첫 호출 비용 제외
    jev_call({"질문": "워밍업", "답변": "워밍업"}, QUESTIONS)
    llm_call(PROMPT_ONE.format(docs="-", q="워밍업", a="워밍업"))
    llm_call(PROMPT_FIVE.format(docs="-", q="워밍업", a="워밍업"))

    lat = {k: {"ms": [], "in": [], "out": [], "reason": []} for k in ("jev1", "llm1", "jev5", "llm5")}
    rows = []
    for r in sample:
        docs = "\n\n".join(as_text(BY_ID[i]) for i in r["docs"]) or "(검색된 문서 없음)"
        state = {"질문": r["q"], "검색된 문서": docs, "답변": r["answer"]}
        rec = {k: r[k] for k in ("q", "group", "grade", "docs")}
        rec["answer"] = r["answer"][:200]

        def jev1():
            ms, ti, to, resp = jev_call(state, ONE)
            rec["p_jev"] = resp.nouls["grounded"].noul
            rec["jev"] = rec["p_jev"] >= 0.5
            return "jev1", ms, ti, to, 0

        def llm1():
            ms, ti, to, rt, text = llm_call(PROMPT_ONE.format(docs=docs, q=r["q"], a=r["answer"]))
            rec["llm"] = text.lower().startswith("yes")
            return "llm1", ms, ti, to, rt

        def jev5():
            ms, ti, to, resp = jev_call(state, QUESTIONS)
            rec["jev5"] = {k: round(resp.nouls[k].noul, 4) for k in QUESTIONS}
            return "jev5", ms, ti, to, 0

        def llm5():
            ms, ti, to, rt, text = llm_call(PROMPT_FIVE.format(docs=docs, q=r["q"], a=r["answer"]))
            rec["llm5_raw"] = text[:300]
            try:
                parsed = json.loads(text.strip().strip("`").removeprefix("json").strip())
                rec["llm5_json_ok"] = set(parsed) == set(QUESTIONS)
            except Exception:
                rec["llm5_json_ok"] = False
            return "llm5", ms, ti, to, rt

        tasks = [jev1, llm1, jev5, llm5]
        rng.shuffle(tasks)
        for t in tasks:
            key, ms, ti, to, rt = t()
            for field, v in (("ms", ms), ("in", ti), ("out", to), ("reason", rt)):
                lat[key][field].append(v)
        rows.append(rec)
    return lat, rows


def main():
    ap = argparse.ArgumentParser(description="13-4 판단 1개 대 5개 측정")
    ap.add_argument("--input", default=str(HERE / "results" / "result_naive.json"),
                    help="evaluate.py --prompt naive 가 만든 답변 캐시")
    ap.add_argument("--split", choices=["dev", "holdout"], required=True)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--limit", type=int, default=None, help="앞 N건만 (점검용)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    src = json.loads(Path(a.input).read_text(encoding="utf-8"))
    sample = src[a.split][:a.limit]
    print(f"입력 {a.input} · {a.split} {len(sample)}건 · LLM {LLM} · 씨앗 {a.seed}")
    lat, rows = measure(sample, seed=a.seed)
    out = {"meta": {"input": Path(a.input).name, "split": a.split, "seed": a.seed,
                    "llm": LLM, "n": len(rows)},
           "latency": lat, "rows": rows}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장: {a.out}  — 표는 aggregate13.py 로 뽑습니다")


if __name__ == "__main__":
    main()
