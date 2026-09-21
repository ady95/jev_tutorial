# -*- coding: utf-8 -*-
"""13-2 실습: 기권을 원인별로 가릅니다.

기권이 전부 같은 이유가 아닙니다. 갈라보면 고칠 것과 고치면 안 될 것이 나뉩니다.

  정당    문서에 답이 없다 (B군)               그대로 둔다
  검색    답은 있는데 다른 문서를 물어왔다       검색을 고치면 풀린다
  생성    맞는 문서를 받고도 답을 미뤘다         생성 쪽 문제다

**판단 모델이 필요 없습니다.** 근거 문서 id가 검색 결과에 있는지만 보면 됩니다.
평가셋에 근거 id를 적어둔 값이 여기서 나옵니다.

    python ch13/run_eval.py          # 먼저 결과 파일을 만들고
    python ch13/diagnose.py ch13_result_word.json
"""
import json
import sys

sys.path.insert(0, ".")


def classify(row):
    if row["group"] == "B":
        return "정당"
    return "생성" if set(row["refs"]) & set(row["docs"]) else "검색"


def recall_at_k(rows):
    need = [r for r in rows if r["group"] != "B"]
    hit = sum(1 for r in need if set(r["refs"]) & set(r["docs"]))
    return hit / len(need)


def report(rows, label):
    ab = [r for r in rows if r["verdict"] == "기권"]
    counts = {}
    for r in ab:
        counts[classify(r)] = counts.get(classify(r), 0) + 1
    print(f"\n[{label}]  기권 {len(ab)}건 / 전체 {len(rows)}건")
    for k in ("정당", "검색", "생성"):
        v = counts.get(k, 0)
        print(f"  {k}  {v:2d}건  {v/len(ab):5.1%}" if ab else f"  {k}   0건")
    print(f"  검색 recall@3  {recall_at_k(rows):.1%}")
    return counts


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "ch13_result_word.json"
    data = json.load(open(path, encoding="utf-8"))

    c1 = report(data["dev"], "개발셋")
    c2 = report(data["holdout"], "검증셋")

    fixable = c1.get("검색", 0) + c2.get("검색", 0) + c1.get("생성", 0) + c2.get("생성", 0)
    total = len(data["dev"]) + len(data["holdout"])
    answered = sum(1 for r in data["dev"] + data["holdout"] if r["verdict"] != "기권")
    print(f"\n  고칠 수 있는 기권    {fixable}건")
    print(f"  현재 coverage       {answered}/{total} = {answered/total:.1%}")
    print(f"  전부 고치면          {(answered + fixable)/total:.1%}")

    print("\n검색이 못 찾은 건")
    n = 0
    for r in data["dev"] + data["holdout"]:
        if r["verdict"] == "기권" and classify(r) == "검색" and n < 6:
            print(f"  근거 {r['refs']}  ->  검색 {r['docs']}")
            print(f"    {r['q']}")
            n += 1
