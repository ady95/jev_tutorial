# -*- coding: utf-8 -*-
"""고객 문의 평가 데이터셋.

책의 4부(보정 측정)와 9부(벤치마크)에서 공통으로 쓰는 평가셋입니다.

정답 라벨은 저자가 직접 부여했습니다. 경계가 애매한 건은 ambiguous=True 로
표시하되, 라벨은 "실무에서 그 부서로 보내는 것이 맞다"는 기준으로 하나만 정했습니다.

여러분의 데이터로 교체하시면 모든 예제가 그 데이터로 돌아갑니다.

부서 정의 (질문의 criteria와 항상 같게 유지하세요):
  billing   요금, 결제, 환불, 세금계산서 관련
  technical 오류, 장애, 사용법, 연동 문제
  sales     구매 상담, 견적, 요금제 문의
  other     위 어디에도 해당하지 않음
"""

# (문의, 정답 부서, 애매한가)
INQUIRIES = [
    # ── billing: 명확 ──────────────────────────────────────────
    ("결제가 두 번 됐습니다. 빨리 환불해주세요.", "billing", False),
    ("이번 달 청구서 금액이 지난달보다 3만원이나 많은데 왜죠?", "billing", False),
    ("세금계산서 발행 부탁드립니다. 사업자번호는 나중에 드릴게요.", "billing", False),
    ("카드가 만료돼서 결제가 실패했다는 메일을 받았습니다.", "billing", False),
    ("작년 12월 영수증을 다시 받을 수 있을까요?", "billing", False),
    ("자동결제를 해지하고 싶습니다.", "billing", False),
    ("환불 신청한 지 2주가 지났는데 아직 입금이 안 됐어요.", "billing", False),
    ("현금영수증 처리가 안 되어 있는데 확인 부탁드립니다.", "billing", False),
    ("결제 수단을 계좌이체로 바꾸려면 어떻게 하나요?", "billing", False),
    ("부가세 별도인가요 포함인가요?", "billing", False),
    ("중간에 해지하면 남은 기간은 일할 계산으로 환불되나요?", "billing", False),
    ("법인카드로 결제했는데 개인카드로 영수증이 발행됐습니다.", "billing", False),

    # ── technical: 명확 ────────────────────────────────────────
    ("앱이 로그인 화면에서 계속 멈춰요. 재설치도 해봤는데 똑같습니다.", "technical", False),
    ("비밀번호 재설정 메일이 안 옵니다. 스팸함도 확인했어요.", "technical", False),
    ("연동 API 문서에 나온 예제가 401 에러를 반환합니다.", "technical", False),
    ("파일 업로드가 50MB 넘으면 실패합니다.", "technical", False),
    ("어제부터 대시보드 그래프가 전혀 안 보입니다.", "technical", False),
    ("웹훅이 간헐적으로 두 번씩 호출됩니다.", "technical", False),
    ("사파리에서만 버튼이 눌리지 않습니다.", "technical", False),
    ("CSV 내보내기를 하면 한글이 깨져서 나옵니다.", "technical", False),
    ("2단계 인증 앱을 바꿨는데 코드가 맞지 않습니다.", "technical", False),
    ("API 응답이 평소보다 10배 느립니다. 장애인가요?", "technical", False),
    ("설정을 저장해도 새로고침하면 원래대로 돌아갑니다.", "technical", False),
    ("SDK를 최신 버전으로 올렸더니 임포트 오류가 납니다.", "technical", False),

    # ── sales: 명확 ────────────────────────────────────────────
    ("기업용 요금제 견적 좀 받아볼 수 있을까요?", "sales", False),
    ("직원 50명 규모인데 어떤 플랜이 적당한가요?", "sales", False),
    ("연간 계약하면 할인이 있나요?", "sales", False),
    ("도입 전에 데모를 볼 수 있을까요?", "sales", False),
    ("경쟁사에서 넘어오려는데 마이그레이션 지원이 되나요?", "sales", False),
    ("교육기관 할인 정책이 있는지 궁금합니다.", "sales", False),
    ("무료 체험 기간을 연장할 수 있을까요?", "sales", False),
    ("엔터프라이즈 플랜에는 전담 지원이 포함되나요?", "sales", False),
    ("파트너사 등록 절차를 알고 싶습니다.", "sales", False),
    ("견적서를 PDF로 보내주실 수 있나요?", "sales", False),

    # ── other: 명확 ────────────────────────────────────────────
    ("그냥 서비스 잘 쓰고 있다고 말씀드리고 싶었어요. 감사합니다!", "other", False),
    ("채용 공고 보고 연락드립니다. 지원 절차가 궁금합니다.", "other", False),
    ("블로그에 서비스 리뷰를 써도 될까요?", "other", False),
    ("개인정보 처리방침 관련해서 문의드립니다.", "other", False),
    ("제휴 마케팅 제안드리고 싶어 연락드렸습니다.", "other", False),
    ("로고 이미지를 발표 자료에 써도 되나요?", "other", False),
    ("탈퇴하면 데이터는 어떻게 되나요?", "other", False),
    ("뉴스레터 수신을 중단하고 싶습니다.", "other", False),

    # ── 스팸/악성 (other로 라우팅) ─────────────────────────────
    ("★★대출 무담보 당일승인★★ 지금 바로 연락주세요", "other", False),
    ("비트코인 투자 수익률 300% 보장합니다. 문의주세요", "other", False),

    # ── 애매한 경계 사례 ───────────────────────────────────────
    ("당장 해지하고 전액 환불 안 해주면 소비자원에 신고하겠습니다.", "billing", True),
    ("쓰던 요금제가 저한테 안 맞는 것 같아요. 어떻게 하죠?", "sales", True),
    ("어제 주문한 거 아직 배송 시작도 안 했던데 언제 오나요", "other", True),
    ("결제는 됐다는데 서비스가 활성화되지 않았습니다.", "technical", True),
    ("플랜을 업그레이드했는데 추가 요금이 얼마나 나오나요?", "billing", True),
    ("무료 플랜에서는 이 기능이 원래 안 되는 건가요?", "sales", True),
    ("계정이 정지됐다는데 이유를 모르겠습니다.", "other", True),
    ("사용량이 갑자기 늘었는데 저희가 뭘 잘못한 걸까요?", "billing", True),
    ("데이터를 옮기려는데 도와주실 분이 있을까요?", "technical", True),
    ("환불은 안 해주셔도 되고요, 그냥 원인만 알려주세요.", "technical", True),
    ("이거 환불 되나요?", "billing", True),
    ("견적서에 적힌 기능이 실제로는 안 되는 것 같습니다.", "technical", True),
    ("담당자분과 통화하고 싶은데 번호를 알 수 있을까요?", "other", True),
    ("계약 갱신 전에 사용량 리포트를 받아볼 수 있나요?", "sales", True),
    ("장애 때문에 못 쓴 기간만큼 보상이 되나요?", "billing", True),
    ("API 호출 한도를 늘리려면 상위 플랜으로 가야 하나요?", "sales", True),
]

LABELS = ["billing", "technical", "sales", "other"]

# 부서 정의. 모든 예제가 이 딕셔너리를 공유합니다.
DEPARTMENTS = {
    "billing": "요금, 결제, 환불, 세금계산서 관련",
    "technical": "오류, 장애, 사용법, 연동 문제",
    "sales": "구매 상담, 견적, 요금제 문의",
    "other": "위 어디에도 해당하지 않음",
}

TEXTS = [t for t, _, _ in INQUIRIES]
TRUTHS = [l for _, l, _ in INQUIRIES]
AMBIGUOUS = [a for _, _, a in INQUIRIES]


def stats():
    from collections import Counter
    c = Counter(TRUTHS)
    amb = sum(AMBIGUOUS)
    return {"total": len(INQUIRIES), "by_label": dict(c),
            "ambiguous": amb, "clear": len(INQUIRIES) - amb}


if __name__ == "__main__":
    s = stats()
    print(f"총 {s['total']}건 (명확 {s['clear']} / 애매 {s['ambiguous']})")
    for k, v in sorted(s["by_label"].items()):
        print(f"  {k:10} {v:3d}건")
