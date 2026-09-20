# Jev 따라하기 — 예제 코드

위키독스 책 **「Jev 따라하기 (LLM과 다른 의사결정 AI 시작하기)」** 의 예제 코드입니다.

- 책: https://wikidocs.net/book/21376

## 빠른 시작

```bash
git clone https://github.com/ady95/jev_tutorial.git
cd jev_tutorial

python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS, Linux

pip install -r requirements.txt
cp .env.example .env          # 키를 채워 넣으세요
```

`.env` 에 필요한 값입니다.

```text
TYPESAFE_API_KEY=발급받은_키
OPENAI_API_KEY=발급받은_키        # LLM 비교 예제에만 필요
```

**변수 이름을 지켜주세요.** SDK가 자동으로 읽는 이름입니다.

## 실행

각 스크립트는 단독으로 실행됩니다. 저장소 루트에서 실행하세요.

```bash
python ch02/first_call.py
python ch03/parallel.py
python ch09/benchmark.py
```

## 구조

| 폴더 | 책의 부 | 내용 |
|---|---|---|
| `dataset/` | 공용 | 평가셋 60건 (부서 라벨 포함) |
| `ch01/` | 1부 | LLM의 한계 실측 |
| `ch02/` | 2부 | 첫 판단 호출 |
| `ch03/` | 3부 | Choice / Noul / Score / 병렬 평가 |
| `ch04/` | 4부 | 보정 측정과 차트 |
| `ch05/` | 5부 | 규칙 엔진 비교, 라우팅, 조합 |
| `ch06/` | 6부 | 하이브리드, 가드레일 |
| `ch07/` | 7부 | RAG 재랭킹, Agent 위험 평가 |
| `ch09/` | 9부 | 4파전 벤치마크 |
| `ch11/` | 11부 | 기권 신호, 신뢰도 통계, 표본 점검, criteria 개선 (전자책 전용 장) |
| `projects/` | 8부 | 완성 프로젝트 4종 |

## 장별 대응표

| 책의 장 | 파일 |
|---|---|
| 01-1 | `ch01/01_text_vs_json.py`, `ch01/03_models.py` |
| 01-2 | `ch01/02_variance.py` |
| 02-2 | `ch02/first_call.py` |
| 03-1 | `ch03/choice.py` |
| 03-2 | `ch03/noul.py` |
| 03-3 | `ch03/score.py` |
| 03-4 | `ch03/parallel.py` |
| 04-2 | `ch04/calibration.py`, `ch04/charts.py` |
| 05-1 | `ch05/smart_if.py` |
| 05-2 | `ch05/routing.py` |
| 05-4 | `ch05/composite.py` |
| 06-2 | `ch06/hybrid.py` |
| 06-4 | `ch06/guardrail.py` |
| 07-1 | `ch07/rag_rerank.py` |
| 07-3 | `ch07/agent_risk.py` |
| 09-1 | `ch09/benchmark.py` |
| 09-4 | `ch09/hybrid_bench.py` |
| 11-2 | `ch11/01_abstain_signals.py` |
| 11-3 | `ch11/02_reliability_stats.py` |
| 11-4 | `ch11/03_audit_sampling.py` |
| 11-5 | `ch11/04_improve_criteria.py` |
| 08-1 | `projects/p1_triage/` |
| 08-2 | `projects/p2_router/` |
| 08-3 | `projects/p3_rag/` |
| 08-4 | `projects/p4_agent/` |

## 주의

**비용이 발생합니다.** `ch09/benchmark.py` 는 판단 60회와 LLM 호출 180회를 합니다. 실행 전에 단가를 확인하세요.

**시간이 걸립니다.** 벤치마크는 5분 이상 걸립니다. 대부분 LLM 호출 대기 시간입니다.

**결과가 책과 다를 수 있습니다.** 모델 버전, 네트워크, 시점이 다르면 숫자가 달라집니다. 그것이 정상이고, 그래서 직접 재는 것입니다.

## 평가셋에 대하여

`dataset/inquiries.py` 의 60건은 **저자가 직접 만들고 라벨링한 것**입니다. 실제 서비스 데이터가 아닙니다.

```python
("결제가 두 번 됐습니다. 빨리 환불해주세요.", "billing", False)
#  문의 내용                                  정답 라벨   애매한가
```

애매한 건 16건을 일부러 섞었습니다. **여러분의 데이터로 교체해서 쓰시는 것을 가장 권합니다.**

```python
# dataset/inquiries.py 를 교체하면 모든 스크립트가 그 데이터로 돌아갑니다
INQUIRIES = [
    ("실제 문의 1", "정답라벨", False),
    ...
]
```

## 기여

오류를 발견하거나 여러분의 환경에서 다른 결과가 나왔다면 이슈로 알려주세요. **여러분이 잰 숫자가 책을 더 정확하게 만듭니다.**

## 라이선스

MIT
