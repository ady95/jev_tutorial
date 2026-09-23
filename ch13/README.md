# ch13 — 프롬프트로 하면 안 되나 (13부)

판단 모델을 붙이려면 의존성이 늘고 호출이 하나 더 생깁니다. 시스템 프롬프트에
한 줄 적어서 될 일이라면 그쪽이 낫습니다. **13부는 그 질문에 실측으로 답합니다.**

같은 일을 프롬프트로도 해보고 판단 모델로도 해봤습니다. 다섯 번 비교했고
**네 번은 프롬프트가 이겼습니다.** 판단 모델이 이긴 한 번은 판단이 여러 개일 때의
**지연시간**이었습니다.

## 가상 데이터입니다

`corpus_tax.py` 의 세무 문서는 **전부 지어낸 것**입니다. 가상 회사의 사내 안내라는
설정이고 조항·금액·기한이 실제 세법과 무관합니다. **실제 세무 판단에 쓰지 마세요.**

여기서 재려는 것은 세법이 아니라 **"답이 문서 안에 있는지 없는지를 시스템이
구분하는가"** 입니다. 문서를 저자가 썼기 때문에 정답 라벨이 설계상 확정됩니다.

## 준비

```bash
pip install langchain langchain-openai langchain-typesafe
```

`.env` 에 `TYPESAFE_API_KEY` 와 `OPENAI_API_KEY` 가 모두 필요합니다.
에이전트 모델은 `TAX_AGENT_MODEL` 로 바꿉니다 (기본값 `openai:gpt-6-luna`).

> **책의 13부 수치는 `gpt-5.6-luna` 로 잰 것입니다.** 기본값은 최신 하위 티어
> 모델로 두었으므로 그대로 돌리면 책과 다른 숫자가 나올 수 있습니다. 책과 같은
> 조건으로 맞추려면 `TAX_AGENT_MODEL=openai:gpt-5.6-luna` 를 주세요.
>
> 책에 실린 수치 자체는 `results/book/` 의 원자료에서 다시 집계할 수 있습니다.
> 모델을 부르지 않으므로 키도 필요 없습니다 — 아래 "책의 수치 다시 집계하기".

## 파일

| 파일 | 하는 일 | 책 |
|---|---|---|
| `corpus_tax.py` | 가상 세무 안내 문서 40건 | 13-1 |
| `dataset_tax.py` | 질문 60건 (개발 30 + 검증 30, A·B·C군) | 13-1 |
| `dataset_d.py` | 조건이 부족한 질문 (되묻기 실험용) | 13-4 |
| `agent_tax.py` | `create_agent` 상담 에이전트. 도구 넷. 첫 프롬프트(`naive`)와 고친 프롬프트(`fixed`) | 13-1, 13-2 |
| `judge_tax.py` | 2단계 채점기와 답변 검증 질문 | 13-1 |
| `evaluate.py` | 60건 실행 + 채점. `--prompt naive/fixed`, `--verify` | 13-1, 13-2 |
| `harness_eval.py` | `AutoModeMiddleware` 로 위험한 도구 막기 | 13-3 |
| `eval_d.py` | 조건 부족 시 되묻는가 — 프롬프트 대 판단 모델 | 13-4 |
| `verify_cost.py` | 판단 1개 대 5개 측정. `--split dev/holdout`, 판정 행 전부 저장 | 13-4 |
| `aggregate13.py` | 측정 파일에서 13-4 의 표를 다시 뽑는다. 모델을 부르지 않는다 | 13-4 |
| `results/book/` | 책에 실린 13-2·13-4 수치의 원자료 | 13-2, 13-4 |

## 평가셋

```text
A군  수록 질문     15+15   문서에 답이 있다      -> 답해야 한다
B군  미수록 질문   10+10   문서에 답이 없다      -> 답하면 안 된다
C군  함정 질문      5+5    비슷한 다른 문서가 걸린다
```

각 항목에 **근거 문서 id를 함께 적어뒀습니다.** 채점기가 정답 근거 문서를 쓸 수
있는 것이 그 덕분입니다.

## 실행 순서

```bash
# 1. 13-1 첫 프롬프트로 60건 -> results/result_naive.json  (13-2 의 순진한 프롬프트 행)
python ch13/evaluate.py --prompt naive

# 2. 13-2 고친 프롬프트로 60건 -> results/result_fixed.json
python ch13/evaluate.py --prompt fixed

# 3. 판단 모델로 답변을 검증해 비교 -> results/result_naive_verify.json
python ch13/evaluate.py --prompt naive --verify

# 4. 모델을 바꿔도 프롬프트가 유지되는지 (책은 이 둘을 비교했습니다)
TAX_AGENT_MODEL=openai:gpt-5.6-luna python ch13/evaluate.py --prompt fixed --out ch13/results/fixed_5.6luna.json
TAX_AGENT_MODEL=openai:gpt-6-luna   python ch13/evaluate.py --prompt fixed --out ch13/results/fixed_6luna.json

# 5. 위험한 도구를 막는 harness
python ch13/harness_eval.py

# 6. 조건이 부족할 때 되묻는가 (세 조건 비교)
python ch13/eval_d.py base
python ch13/eval_d.py prompt
python ch13/eval_d.py jev

# 7. 판단 1개 대 5개 — 1번의 답변을 입력으로, 개발셋으로 재고 홀드아웃으로 확인
python ch13/verify_cost.py --split dev     --out ch13/results/cost_dev.json
python ch13/verify_cost.py --split holdout --out ch13/results/cost_holdout.json
python ch13/aggregate13.py ch13/results/cost_dev.json ch13/results/cost_holdout.json
```

7번의 입력은 **1번이 만든 `result_naive.json`** 입니다. 고친 프롬프트의 답변을
넣으면 13-4 가 비교한 답변 집합과 조건이 달라집니다. 홀드아웃은 한 번만
확인하세요. 여러 번 들여다보면 그것도 개발셋이 됩니다.

어느 단계든 `--limit 3` 을 주면 셋마다 앞 3건만 돌려 배선만 확인할 수 있습니다.

## 책의 수치 다시 집계하기

```bash
python ch13/aggregate13.py
```

인자 없이 돌리면 `results/book/` 의 세 측정 파일을 읽어 13-4 의 지연 비율 표,
판단 하나의 정확도 53/60, 경계 구간 표, 불일치 문항 겹침을 출력합니다.

| 파일 | 무엇인가 |
|---|---|
| `result_naive.json` | 13-1 첫 프롬프트의 60건 답변과 채점. 13-4 측정의 입력 |
| `result_fixed.json` | 13-2 고친 프롬프트의 60건 답변과 채점 |
| `cost_dev_run1.json` | 13-4 1차 개발셋 측정. 지연과 불일치만 남아 있음 |
| `cost_dev_run2.json` | 13-4 2차 개발셋 측정. 판정 행 전부 |
| `cost_holdout.json` | 13-4 홀드아웃 측정. 판정 행 전부 |

## 같은 값이 나오지 않는 것이 정상입니다

생성 모델이 바뀌면 답변 문장이 달라지고 채점 결과도 따라 바뀝니다. 지연시간은
회선과 시각에 좌우됩니다. **자릿수와 방향이 같으면 재현된 것으로 봅니다.**

같은 개발셋을 두 번 쟀을 때 두 방식의 판정이 어긋난 문항은 5건과 3건이었고,
**3건 모두 되풀이**됐습니다. 1차에만 나온 2건은 한 번의 흔들림일 수 있습니다.
개별 건을 근거로 삼으려면 반복해서 나오는지부터 보세요.
