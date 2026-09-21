# -*- coding: utf-8 -*-
"""13-2, 13-3 실습: 검색기를 recall로 비교합니다.

**recall은 모델을 부르지 않고 잴 수 있습니다.** 근거 문서 id가 검색 결과에
있는지만 보면 되기 때문입니다. 그래서 검색기는 공짜로 여러 번 고칠 수 있습니다.

생성까지 돌려야 알 수 있는 지표(coverage, 신뢰도)는 비쌉니다.
**싼 지표로 먼저 후보를 좁히고, 비싼 지표는 마지막에 한 번만 잽니다.**

    python ch13/retrievers.py
"""
import re
import sys

sys.path.insert(0, ".")
from ch13.corpus_tax import CORPUS
from ch13.dataset_tax import TAX_DEV, TAX_HOLDOUT

DOC_TEXT = {d[0]: f"{d[1]} {d[2]} {d[3]}" for d in CORPUS}
IDS = [d[0] for d in CORPUS]


# ---------- 1. 낱말 겹침 (기준선) ----------
def _tokens(text):
    return set(re.findall(r"[가-힣A-Za-z0-9]{2,}", text))


def retrieve_word(question, k=3):
    """agent_tax.retrieve_docs 와 같은 방식. 문서 id만 돌려줍니다."""
    q = _tokens(question)
    scored = []
    for doc in CORPUS:
        overlap = len(q & _tokens(f"{doc[2]} {doc[3]}"))
        if overlap:
            scored.append((overlap / (len(q) ** 0.5 + 1), doc[0]))
    scored.sort(key=lambda x: -x[0])
    return [i for _, i in scored[:k]]


# ---------- 2. 문자 3-gram ----------
def _ngrams(text, n=3):
    text = re.sub(r"\s+", "", text)
    return {text[i:i + n] for i in range(len(text) - n + 1)}


DOC_NG = {i: _ngrams(DOC_TEXT[i]) for i in IDS}


def retrieve_char(question, k=3, floor=0.02):
    """문자 단위로 끊어 조사 문제를 우회합니다. 모델도 API도 필요 없습니다."""
    qg = _ngrams(question)
    if not qg:
        return []
    scored = []
    for doc_id in IDS:
        inter = len(qg & DOC_NG[doc_id])
        if inter:
            # 질문 쪽으로 정규화 — 긴 문서가 무조건 이기지 않게
            scored.append((inter / len(qg), doc_id))
    scored = [(s, i) for s, i in scored if s >= floor]
    scored.sort(reverse=True)
    return [i for _, i in scored[:k]]


# ---------- 평가 ----------
def recall_at_k(dataset, fn, k=3):
    """근거 문서를 상위 k개 안에 물어왔나. B군은 근거가 없으므로 뺍니다."""
    need = [r for r in dataset if r[1] != "B"]
    hit = sum(1 for q, g, refs, _ in need if set(refs) & set(fn(q, k)))
    return hit / len(need)


def empty_rate_on_b(dataset, fn, k=3):
    """B군에서 빈 결과를 내는 비율. 낮으면 엉뚱한 문서를 주고 있다는 뜻입니다."""
    bs = [r for r in dataset if r[1] == "B"]
    return sum(1 for q, g, refs, _ in bs if not fn(q, k)) / len(bs)


if __name__ == "__main__":
    print(f"{'검색기':14} {'개발 recall@3':>13} {'검증 recall@3':>13} {'B군 빈결과율':>13}")
    for label, fn in (("낱말 겹침", retrieve_word), ("문자 3-gram", retrieve_char)):
        rd = recall_at_k(TAX_DEV, fn)
        rh = recall_at_k(TAX_HOLDOUT, fn)
        be = (empty_rate_on_b(TAX_DEV, fn) + empty_rate_on_b(TAX_HOLDOUT, fn)) / 2
        print(f"{label:14} {rd:12.1%} {rh:13.1%} {be:13.1%}")

    print("\n낱말이 놓치고 문자가 잡은 건")
    n = 0
    for q, g, refs, _ in TAX_DEV + TAX_HOLDOUT:
        if g == "B" or n >= 5:
            continue
        w, c = set(retrieve_word(q)), set(retrieve_char(q))
        if not set(refs) & w and set(refs) & c:
            print(f"  {q}")
            print(f"    낱말 {sorted(w)}  ->  문자 {sorted(c)}")
            n += 1

    print("\nrecall만 보고 좋아하면 안 됩니다.")
    print("B군 빈결과율이 떨어졌다는 것은 답이 없는 질문에도 문서를 물어온다는 뜻이고,")
    print("거기서 날조가 생깁니다. 13-3 참고.")
