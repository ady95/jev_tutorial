# 프로젝트 4 — AI Agent Decision Layer

책의 08-4에 대응합니다. 난이도 별 넷. 이 책의 모든 내용이 들어갑니다.

```bash
python projects/p4_agent/agent.py
```

## 구조

```
요청 → Jev (도구/정보/완료/위험 5가지를 한 호출로)
     → Policy (순수 함수)
     → execute / approve / escalate / block / ask_user
     → LLM (인자 생성, 답변 작성)
     → Jev (결과 검증)
```

## 이 프로젝트의 핵심

`decide()` 가 **순수 함수**라는 점입니다. 네트워크도 부작용도 없으므로
단위 테스트를 쓸 수 있고, 저장된 판단으로 과거를 재현할 수 있습니다.

```bash
python -m pytest projects/p4_agent/test_policy.py    # pytest가 있다면
python projects/p4_agent/test_policy.py              # 없어도 실행됩니다
```

## 과한 구조일 수도 있습니다

도구가 두세 개이고 전부 읽기 전용이라면 LLM 함수 호출로 충분합니다.
**되돌릴 수 없는 행동이 있을 때** 값어치를 합니다.
