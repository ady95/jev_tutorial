# -*- coding: utf-8 -*-
"""검증셋(holdout) 60건.

기존 60건(dataset/inquiries.py)은 **개발셋**으로 쓴다: 후보 정의를 다듬고
임계값을 고르는 데 사용한다.

이 파일의 60건은 **검증셋**이다: 임계값을 고른 뒤 최종 성능을 보고할 때만 쓴다.
개발셋으로 정한 것을 검증셋에서 확인하는 구조여야 과적합을 피할 수 있다.

1차 검수 H5 지적("같은 60건으로 임계값을 정하고 성능까지 평가했다")에 대한 대응.

작성 원칙:
- 개발셋과 같은 부서 정의, 비슷한 라벨 분포
- 애매한 경계 사례를 같은 비율(약 27%)로 포함
- 개발셋의 문장을 변형하지 않고 새로 작성 (겹치면 검증의 의미가 없다)
- PDF 변환을 고려해 장식 문자(별표 등)를 쓰지 않는다
"""

# (문의, 정답 부서, 애매한가)
HOLDOUT = [
    # ── billing: 명확 ──────────────────────────────────────────
    ("이번 결제분 카드 승인이 취소됐다는 문자를 받았습니다.", "billing", False),
    ("연간 결제했는데 월 단위로 청구된 것 같습니다.", "billing", False),
    ("계산서에 적힌 공급가액이 맞는지 확인 부탁드립니다.", "billing", False),
    ("할인 쿠폰을 넣었는데 적용이 안 된 채로 결제됐어요.", "billing", False),
    ("결제일을 매월 25일로 바꿀 수 있나요?", "billing", False),
    ("작년 연말정산용 납부확인서가 필요합니다.", "billing", False),
    ("두 계정 요금을 하나로 합쳐서 청구받고 싶습니다.", "billing", False),
    ("해지했는데 다음 달에도 청구가 됐습니다.", "billing", False),
    ("환급 계좌를 다른 은행으로 변경하고 싶습니다.", "billing", False),
    ("초과 사용분 단가가 어떻게 계산되는지 알려주세요.", "billing", False),
    ("세금계산서 역발행으로 처리해주실 수 있나요?", "billing", False),
    ("결제 영수증에 회사명이 잘못 들어가 있습니다.", "billing", False),

    # ── technical: 명확 ────────────────────────────────────────
    ("모바일에서 첨부파일을 열면 앱이 종료됩니다.", "technical", False),
    ("SSO 로그인 후 권한이 없다고 나옵니다.", "technical", False),
    ("배치 작업이 자정에 실행되지 않고 건너뜁니다.", "technical", False),
    ("검색 결과가 최근 사흘치만 나옵니다.", "technical", False),
    ("웹소켓 연결이 30초마다 끊깁니다.", "technical", False),
    ("PDF로 내보내면 표 테두리가 사라집니다.", "technical", False),
    ("동일 요청을 보냈는데 429 응답이 계속 옵니다.", "technical", False),
    ("관리자 계정으로도 설정 메뉴가 보이지 않습니다.", "technical", False),
    ("알림이 중복으로 세 번씩 도착합니다.", "technical", False),
    ("타임존이 UTC로 고정되어 한국 시간과 아홉 시간 차이가 납니다.", "technical", False),
    ("대용량 조회를 하면 게이트웨이 타임아웃이 납니다.", "technical", False),
    ("업데이트 후 기존 토큰이 전부 무효가 됐습니다.", "technical", False),

    # ── sales: 명확 ────────────────────────────────────────────
    ("비영리 단체인데 적용 가능한 요금 정책이 있을까요?", "sales", False),
    ("연간 선결제하면 몇 퍼센트 할인되나요?", "sales", False),
    ("제안서에 넣을 기능 목록을 받을 수 있을까요?", "sales", False),
    ("사내 보안 검토용으로 SOC 보고서를 받고 싶습니다.", "sales", False),
    ("좌석 수를 20개에서 80개로 늘리려면 절차가 어떻게 되나요?", "sales", False),
    ("온프레미스 설치형도 제공하시나요?", "sales", False),
    ("PoC를 한 달 진행하고 싶은데 지원이 되나요?", "sales", False),
    ("리셀러로 참여하려면 어떤 조건이 필요한가요?", "sales", False),
    ("교육용 라이선스 신청 서류를 안내받고 싶습니다.", "sales", False),
    ("기존 계약을 3년으로 연장하면 단가가 달라지나요?", "sales", False),

    # ── other: 명확 ────────────────────────────────────────────
    ("서비스 소개를 사내 세미나에서 다뤄도 괜찮을까요?", "other", False),
    ("보도자료에 인용할 수 있는 담당자 코멘트를 받고 싶습니다.", "other", False),
    ("개발자 채용 중이신지 궁금합니다.", "other", False),
    ("제 계정에 저장된 개인정보 사본을 요청합니다.", "other", False),
    ("오탈자를 발견해서 알려드립니다. 도움말 3페이지입니다.", "other", False),
    ("그동안 잘 썼습니다. 팀이 해체돼서 인사드립니다.", "other", False),
    ("설문조사 참여 안내 메일을 그만 받고 싶습니다.", "other", False),
    ("컨퍼런스 후원사로 참여하실 의향이 있으신가요?", "other", False),

    # ── 스팸 (other) — 장식 문자 없이 ──────────────────────────
    ("급전 필요하신 분 무직자도 당일 가능 지금 문의주세요", "other", False),
    ("해외선물 리딩방 무료체험 수익 인증 확인하세요", "other", False),

    # ── 애매한 경계 사례 ───────────────────────────────────────
    ("요금이 왜 이렇게 나왔는지 모르겠고 해지하고 싶습니다.", "billing", True),
    ("지금 플랜으로는 부족한데 어떻게 해야 할지 모르겠어요.", "sales", True),
    ("주문한 상품이 아직 도착하지 않았습니다.", "other", True),
    ("결제는 완료됐는데 좌석이 늘어나지 않았습니다.", "technical", True),
    ("업그레이드하면 지금 데이터는 그대로 유지되나요?", "sales", True),
    ("무료 플랜 제한에 걸린 건지 오류인지 구분이 안 됩니다.", "technical", True),
    ("계약서에 적힌 가용성 기준을 못 지킨 것 같습니다.", "billing", True),
    ("API 호출이 갑자기 늘었는데 요금 폭탄 맞을까요?", "billing", True),
    ("다른 서비스로 옮기려는데 데이터를 어떻게 빼나요?", "technical", True),
    ("환불받고 싶지는 않고 왜 이렇게 됐는지만 알고 싶습니다.", "technical", True),
    ("이거 무료인가요?", "sales", True),
    ("데모에서 본 기능이 실제 계정에는 없습니다.", "technical", True),
    ("책임자와 직접 이야기하고 싶습니다.", "other", True),
    ("갱신 시점에 좌석을 줄이면 환불이 되나요?", "billing", True),
    ("장애 공지를 못 받았는데 알림 설정 문제인가요?", "technical", True),
    ("상위 플랜에만 있는 기능을 미리 써볼 수 있나요?", "sales", True),
]

LABELS = ["billing", "technical", "sales", "other"]

TEXTS = [t for t, _, _ in HOLDOUT]
TRUTHS = [l for _, l, _ in HOLDOUT]
AMBIGUOUS = [a for _, _, a in HOLDOUT]


def stats():
    from collections import Counter
    c = Counter(TRUTHS)
    amb = sum(AMBIGUOUS)
    return {"total": len(HOLDOUT), "by_label": dict(c),
            "ambiguous": amb, "clear": len(HOLDOUT) - amb}


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    s = stats()
    print(f"검증셋 총 {s['total']}건 (명확 {s['clear']} / 애매 {s['ambiguous']})")
    for k, v in sorted(s["by_label"].items()):
        print(f"  {k:10} {v:3d}건")
