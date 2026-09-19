# 프로젝트 3 — RAG 품질검사 시스템

책의 08-3에 대응합니다. 난이도 별 셋.

판단 계층이 **세 곳**에 들어갑니다.

```
질문 → 벡터 검색 → [1] 관련성 판정 → 재랭킹 → [2] 답변 가능 판정 → LLM → [3] 근거 검증 → 응답
```

```bash
python projects/p3_rag/pipeline.py
```

## 벡터 검색 붙이기

`pipeline.py` 의 `search()` 는 데모용 고정 문서를 돌려줍니다.
여러분의 검색기로 교체하세요.

```python
def search(query, k=8):
    return your_vector_store.similarity_search(query, k=k)
```

## 도입 전에

`evaluate()` 로 재랭킹 전후의 precision@k 를 재보세요.
**개선폭이 없으면 판정 비용만 늘어납니다.**
