# -*- coding: utf-8 -*-
"""3-5 실험: 이미지와 Box — 정답을 아는 합성 이미지로 재기.

실험 기능입니다. typesafe-sdk 0.7.5 이상과 jev-1.14.0 이 필요합니다.
책의 기준 SDK(0.7.0)와 섞이지 않게 가상환경을 따로 만드시기를 권합니다(3-5 「준비」).

    pip install "typesafe-sdk[pil]==0.7.5" python-dotenv
    python ch03/box_shapes.py                  책의 3-5 전체 실험 (API 약 62회)
    python ch03/box_shapes.py --out box.json   건별 결과 저장

재는 것 — 책 3-5 의 표 전부:
  헤더 없이 보냈을 때, jev-1.13.0 에 Box 를 보냈을 때 (둘 다 거절되는지)
  빨간 원 있음 20장 / 없음 10장: Box 위치(IoU), 영어 지시, Noul 존재 확인, 지연·입력 토큰
  앞 10장에서 고른 임계값을 뒤 10장에서 확인
시드를 고정해 책과 같은 이미지를 그립니다. 모델 출력은 실행마다 조금씩 달라질 수 있습니다.
책의 원자료는 ch03/results/book/box_2026-10-19.json 입니다.
"""
import argparse
import json
import random
import statistics
import time

from dotenv import load_dotenv
from PIL import Image as PILImage, ImageDraw

load_dotenv()
from typesafe_sdk import Box, Image, Noul, TypeSafeClient

W, H = 640, 480
MODEL = "jev-1.14.0"
HDR = {"TypeSafe-Danger-Zone-Images": "true"}       # 이미지·Box 요청에는 매번 필요
GRID = (0.5, 0.7, 0.8, 0.9, 0.95)
Q = {"box": Box(instructions="빨간 원"),
     "has": Noul(instructions="이미지에 빨간 원이 있는가?",
                 criteria={"true": "빨간색 원이 하나 이상 보인다", "false": "빨간색 원이 없다"})}
Q_EN = {"box": Box(instructions="The red circle")}


def draw(seed, with_target):
    """파란 사각형·회색 삼각형, 그리고 (있으면) 빨간 원을 겹치지 않게 그린다.

    반환: (PIL 이미지, 정답 상자 또는 None). 좌표는 0~1 비율, 원점은 왼쪽 위.
    """
    rnd = random.Random(seed)
    im = PILImage.new("RGB", (W, H), "white")
    g = ImageDraw.Draw(im)
    boxes = []

    def place(size):
        while True:
            x, y = rnd.randint(10, W - size - 10), rnd.randint(10, H - size - 10)
            b = (x, y, x + size, y + size)
            if all(b[2] < o[0] or b[0] > o[2] or b[3] < o[1] or b[1] > o[3] for o in boxes):
                boxes.append(b)
                return b

    b = place(rnd.randint(70, 130)); g.rectangle(b, fill=(40, 90, 220))
    b = place(rnd.randint(70, 130))
    g.polygon([(b[0], b[3]), ((b[0] + b[2]) // 2, b[1]), (b[2], b[3])], fill=(150, 150, 150))
    truth = None
    if with_target:
        b = place(rnd.randint(60, 140)); g.ellipse(b, fill=(220, 30, 30))
        truth = {"left": b[0] / W, "top": b[1] / H, "right": b[2] / W, "bottom": b[3] / H}
    return im, truth


def iou(a, b):
    ix = max(0, min(a["right"], b["right"]) - max(a["left"], b["left"]))
    iy = max(0, min(a["bottom"], b["bottom"]) - max(a["top"], b["top"]))
    inter = ix * iy
    area = lambda r: (r["right"] - r["left"]) * (r["bottom"] - r["top"])
    return inter / (area(a) + area(b) - inter) if inter else 0.0


def edges(answer):
    return {k: getattr(answer.box, k) for k in ("left", "top", "right", "bottom")}


def check_rejections(client):
    im, _ = draw(0, True)
    for label, kwargs in (("헤더 없이", {"model": MODEL}),
                          ("jev-1.13.0 에 Box", {"model": "jev-1.13.0", "extra_headers": HDR})):
        try:
            client.system_one(state=Image.from_pil(im), questions={"box": Box(instructions="빨간 원")}, **kwargs)
            print(f"{label}: 통과")
        except Exception as e:
            print(f"{label}: {type(e).__name__} {str(e)[:80]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None, help="건별 결과를 저장할 JSON 경로")
    a = ap.parse_args()

    rows = []
    with TypeSafeClient() as client:
        check_rejections(client)
        for kind, seeds in (("present", range(1, 21)), ("absent", range(101, 111))):
            for seed in seeds:
                im, truth = draw(seed, kind == "present")
                t0 = time.perf_counter()
                r = client.system_one(state=Image.from_pil(im), questions=Q, model=MODEL, extra_headers=HDR)
                ms = (time.perf_counter() - t0) * 1000
                r_en = client.system_one(state=Image.from_pil(im), questions=Q_EN, model=MODEL, extra_headers=HDR)
                box, box_en = edges(r.boxes["box"]), edges(r_en.boxes["box"])
                rows.append({"kind": kind, "seed": seed, "box": box, "conf": r.boxes["box"].confidence,
                             "has": r.nouls["has"].noul, "iou": iou(box, truth) if truth else None,
                             "iou_en": iou(box_en, truth) if truth else None,
                             "conf_en": r_en.boxes["box"].confidence, "ms": ms,
                             "model": r.model, "in_tok": r.usage.input_tokens})

    pres = [r for r in rows if r["kind"] == "present"]
    absn = [r for r in rows if r["kind"] == "absent"]
    print(f"\n응답 모델 {sorted({r['model'] for r in rows})}")
    print(f"빨간 원 위치  IoU 0.5 이상 {sum(r['iou'] >= 0.5 for r in pres)}/{len(pres)}  "
          f"IoU 중앙값 {statistics.median(r['iou'] for r in pres):.2f}  "
          f"영어 지시 {sum(r['iou_en'] >= 0.5 for r in pres)}/{len(pres)}")
    print(f"Noul 있는가  원 있음 최소 {min(r['has'] for r in pres):.2f}  원 없음 최대 {max(r['has'] for r in absn):.2f}")
    print(f"원이 없을 때 Box confidence {min(r['conf'] for r in absn):.2f}~{max(r['conf'] for r in absn):.2f} "
          f"(상자는 항상 돌아온다)")
    print(f"지연 중앙값 {statistics.median(r['ms'] for r in rows):.0f}ms  "
          f"입력 토큰 중앙값 {statistics.median(r['in_tok'] for r in rows):.0f}")

    dev, hold = pres[:10], pres[10:]           # 앞 10장에서 고르고 뒤 10장에서 확인
    th = next((t for t in GRID
               if [r for r in dev if r["conf"] >= t] and all(r["iou"] >= 0.5 for r in dev if r["conf"] >= t)), None)
    print(f"\n개발 10장에서 고른 임계값 {th}")
    if th is not None:
        g = [r for r in hold if r["conf"] >= th]
        print(f"검증 10장  통과 {len(g)}장, 그중 IoU 0.5 이상 {sum(r['iou'] >= 0.5 for r in g)}장")

    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)
        print(f"저장: {a.out}")


if __name__ == "__main__":
    main()
