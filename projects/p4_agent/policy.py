# -*- coding: utf-8 -*-
"""Agent 정책. 순수 함수 — 네트워크도 부작용도 없다."""
from dataclasses import dataclass, field


@dataclass
class Judgment:
    tool: str
    confidence: float
    alternatives: dict = field(default_factory=dict)
    ready: bool = True
    done: bool = False
    reversible: float = 1.0
    impact: float = 0.0
    latency_ms: float = 0.0
    model: str = ""


READ_ONLY = {"search_docs", "get_order", "get_billing"}
DESTRUCTIVE = {"delete_account", "run_sql"}
AUTO_REFUND_LIMIT = 1_000_000
CONFIDENCE_FLOOR = 0.60


def decide(j: Judgment, args: dict | None = None) -> tuple[str, str]:
    """(행동, 사유)를 돌려준다. 실행하지 않는다."""
    if j.done:
        return "finish", "요청을 처리할 정보를 모두 확보"
    if j.confidence < CONFIDENCE_FLOOR:
        return "escalate", f"도구를 특정할 수 없음 (conf {j.confidence})"
    if j.tool == "escalate":
        return "escalate", "모델이 사람 개입을 요청"
    if not j.ready:
        return "ask_user", "필요한 정보 부족"

    if j.tool in READ_ONLY:
        return "execute", "읽기 전용"
    if j.tool in DESTRUCTIVE or j.impact >= 2.5:
        return "block", f"파괴적 행동 (impact {j.impact})"

    amount = (args or {}).get("amount")
    if amount is not None and amount > AUTO_REFUND_LIMIT:
        return "approve", f"한도 초과 금액 {amount:,}"

    if j.reversible < 0.3 or j.impact >= 1.5:
        return "approve", f"되돌릴 수 없거나 영향이 큼 (rev {j.reversible})"

    return "execute", "안전한 변경"
