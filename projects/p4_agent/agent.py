# -*- coding: utf-8 -*-
"""프로젝트 4: AI Agent Decision Layer.

도구 실행은 데모용 스텁입니다. 실제 도구로 교체해서 쓰세요.
"""
import os
import sys
import time
from dataclasses import asdict

sys.path.insert(0, ".")
sys.path.insert(0, os.path.dirname(__file__))
from _common import require_jev, warmup_jev
from policy import Judgment, decide

require_jev()
from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

TOOLS = {
    "search_docs": "제품 문서나 FAQ에서 정보를 찾는다",
    "get_order": "주문 번호로 주문 상태와 내역을 조회한다",
    "get_billing": "청구 내역과 결제 수단을 조회한다",
    "issue_refund": "환불을 실행한다",
    "send_email": "고객에게 이메일을 보낸다",
    "escalate": "사람 상담원에게 넘긴다",
}

STEP = {
    "tool": Choice(criteria=TOOLS),
    "has_enough_info": Noul(
        instructions="이 도구를 실행하는 데 필요한 정보가 다 있는가?",
        criteria={"true": "주문번호, 금액 등 필요한 값이 제시되어 있다",
                  "false": "값이 빠져 있어 되물어야 한다"}),
    "done": Noul(
        instructions="지금까지의 결과로 사용자 요청에 답할 수 있는가?",
        criteria={"true": "필요한 정보를 모두 얻었다",
                  "false": "아직 더 조회하거나 실행할 것이 남았다"}),
    "reversible": Noul(
        instructions="이 행동은 되돌릴 수 있는가?",
        criteria={"true": "취소하거나 원상복구할 수 있다",
                  "false": "한번 실행하면 되돌릴 수 없거나 외부에 노출된다"}),
    "impact": Score(criteria=["영향 없음 또는 읽기만 함", "되돌릴 수 있는 변경",
                              "금전이나 외부 발송이 발생", "데이터 삭제나 복구 불가"]),
}

MAX_STEPS = 4


class Tools:
    """도구를 실행하는 유일한 경로. 검사를 우회할 수 없게 한다."""

    REGISTRY = {
        "search_docs": lambda **kw: "환불은 결제일로부터 7일 이내 신청해야 합니다.",
        "get_order": lambda **kw: {"order_id": "A-1024", "amount": 39000, "status": "배송완료"},
        "get_billing": lambda **kw: {"last_payment": 39000, "method": "card"},
        "issue_refund": lambda **kw: {"refunded": True},
        "send_email": lambda **kw: {"sent": True},
    }

    def __init__(self):
        self.audit = []

    def run(self, tool, args):
        if tool not in self.REGISTRY:
            raise ValueError(f"등록되지 않은 도구: {tool}")
        result = self.REGISTRY[tool](**(args or {}))
        self.audit.append({"tool": tool, "args": args})
        return result


def judge_step(context, client) -> Judgment:
    t0 = time.perf_counter()
    r = client.system_one(state=context, questions=STEP)
    ms = (time.perf_counter() - t0) * 1000
    t = r.choices["tool"]
    return Judgment(
        tool=t.choice, confidence=round(t.confidence, 3),
        alternatives={k: round(v, 3) for k, v in
                      sorted(t.probabilities.items(), key=lambda kv: -kv[1])[:3]},
        ready=r.nouls["has_enough_info"].noul >= 0.7,
        done=r.nouls["done"].noul >= 0.7,
        reversible=round(r.nouls["reversible"].noul, 3),
        impact=round(r.scores["impact"].score, 2),
        latency_ms=round(ms), model=r.model)


def extract_args(context, tool):
    """데모용. 실제로는 LLM에게 인자를 만들게 합니다."""
    if tool == "get_order":
        return {"order_id": "A-1024"}
    if tool == "issue_refund":
        return {"amount": 39000}
    if tool == "search_docs":
        return {"query": "환불 정책"}
    return {}


def explain(trace):
    lines = []
    for e in trace:
        j = e["judgment"]
        lines.append(f"{e['step']}단계: {j['tool']} 선택 (확신 {j['confidence']}, "
                     f"되돌림 {j['reversible']}, 영향 {j['impact']}) "
                     f"-> {e['action']} ({e['reason']})")
    return "\n".join(lines)


def run_agent(request, client, tools):
    context = {"요청": request, "지금까지": []}
    trace = []

    for step in range(MAX_STEPS):
        j = judge_step(context, client)
        args = extract_args(context, j.tool) if (j.ready and not j.done) else None
        action, reason = decide(j, args)
        trace.append({"step": step, "judgment": asdict(j), "args": args,
                      "action": action, "reason": reason})

        if action in ("finish", "escalate", "block", "ask_user", "approve"):
            return {"status": action, "reason": reason, "trace": trace}

        result = tools.run(j.tool, args)
        context["지금까지"].append({"도구": j.tool, "인자": args, "결과": result})

    return {"status": "escalate", "reason": "최대 단계 초과", "trace": trace}


def main():
    requests = [
        "주문 A-1024 환불해주세요. 배송이 너무 늦었습니다.",
        "환불 규정이 어떻게 되나요?",
    ]

    tools = Tools()
    with TypeSafeClient() as client:
        warmup_jev(client, STEP["done"])
        for req in requests:
            print(f"\n요청: {req}")
            out = run_agent(req, client, tools)
            print(explain(out["trace"]))
            print(f"결과: {out['status']} — {out['reason']}")

    print("\ntrace에 모든 판단값이 남습니다.")
    print("'왜 환불을 자동 실행하지 않았나'에 답할 수 있는 유일한 수단입니다.")


if __name__ == "__main__":
    main()
