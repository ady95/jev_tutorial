# 프로젝트 1 — 고객문의 자동 분류 시스템

책의 08-1에 대응합니다. 난이도 별 하나.

판단 한 번으로 다섯 가지를 알아내고, 그 결과에 따라 네 갈래로 보냅니다.

```bash
python projects/p1_triage/triage.py
```

## 구조

```
문의 → Jev (5가지 판단) → 정책 코드 → quarantine / escalate / refund_flow / auto_route / review
```

판단 로그가 `out/tickets.json` 에 저장됩니다. `replay.py` 로 정책만 바꿔
과거를 재현할 수 있습니다 (API 호출 없음).

```bash
python projects/p1_triage/replay.py
```
