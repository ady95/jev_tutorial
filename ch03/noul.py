# -*- coding: utf-8 -*-
"""03-2 실습: Noul — 확률 하나에 판단과 확신도가 함께 들어 있다."""
import sys

sys.path.insert(0, ".")
from _common import require_jev, warmup_jev

require_jev()
from typesafe_sdk import Noul, TypeSafeClient

REFUND = Noul(instructions="고객이 환불이나 결제 취소를 요구하고 있는가?")

REFUND_STRICT = Noul(
    instructions="고객이 환불이나 결제 취소를 요구하고 있는가?",
    criteria={"true": "환불이나 결제 취소를 실제로 요청하고 있다",
              "false": "가능 여부나 정책을 묻기만 하거나, 환불을 원하지 않거나, 무관하다"})

CASES = [
    ("전액 환불해주세요", "명백한 요구"),
    ("결제 취소 부탁드립니다", "다른 표현"),
    ("환불은 안 해주셔도 되고요, 그냥 원인만 알려주세요", "부정문 함정"),
    ("서비스가 별로네요", "불만이지만 요구 아님"),
    ("이거 환불 되나요?", "요구인가 문의인가"),
    ("로그인이 안 됩니다", "무관"),
]


def main():
    with TypeSafeClient() as client:
        warmup_jev(client, REFUND)

        print(f"{'설명만':>8} {'criteria 추가':>14}  문의")
        for text, note in CASES:
            a = client.system_one(state=text, questions={"r": REFUND}).nouls["r"].noul
            b = client.system_one(state=text, questions={"r": REFUND_STRICT}).nouls["r"].noul
            print(f"{a:8.2f} {b:14.2f}  {text}  ({note})")

        print("\ncriteria로 경계를 명시하면 애매한 건의 값이 달라집니다.")
        print("특히 '이거 환불 되나요?' 같은 문의에서 차이가 큽니다.")
        print("\n임계값 설계 예시:")
        print("  > 0.9   자동 처리")
        print("  > 0.5   사람이 확인   <- 중간 구간을 버리지 마세요")
        print("  그 외    환불 건 아님")


if __name__ == "__main__":
    main()
