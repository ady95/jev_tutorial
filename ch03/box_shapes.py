# -*- coding: utf-8 -*-
"""3-5 실험: 이미지와 Box — 정답을 아는 합성 이미지로 재기.

실험 기능입니다. typesafe-sdk 0.7.5 이상과 jev-1.14.0 이 필요합니다.
책의 기준 SDK(0.7.0)와 섞이지 않게 가상환경을 따로 만드시기를 권합니다.

    pip install "typesafe-sdk[pil]==0.7.5" python-dotenv
    python ch03/box_shapes.py

시드를 고정해 책과 같은 이미지 30장(빨간 원 있음 20, 없음 10)을 다시 그립니다.
"""
import random
import statistics

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


def draw(seed, with_target):
    """파란 사각형·회색 삼각형, 그리고 (있으면) 빨간 원을 겹치지 않게 그린다."""
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


def main():
    present, absent = [], []
    with TypeSafeClient() as client:
        for kind, seeds in (("present", range(1, 21)), ("absent", range(101, 111))):
            for seed in seeds:
                im, truth = draw(seed, kind == "present")
                r = client.system_one(state=Image.from_pil(im), questions=Q, model=MODEL, extra_headers=HDR)
                bx = r.boxes["box"]
                box = {k: getattr(bx.box, k) for k in ("left", "top", "right", "bottom")}
                row = {"seed": seed, "conf": bx.confidence, "has": r.nouls["has"].noul}
                if truth:
                    row["iou"] = iou(box, truth)
                    present.append(row)
                else:
                    absent.append(row)

    print(f"빨간 원 위치  IoU 0.5 이상 {sum(r['iou'] >= 0.5 for r in present)}/{len(present)}  "
          f"IoU 중앙값 {statistics.median(r['iou'] for r in present):.2f}")
    print(f"Noul 있는가  원 있음 최소 {min(r['has'] for r in present):.2f}  원 없음 최대 {max(r['has'] for r in absent):.2f}")
    print(f"원이 없을 때 Box confidence {min(r['conf'] for r in absent):.2f}~{max(r['conf'] for r in absent):.2f} "
          f"(상자는 항상 돌아온다)")

    dev, hold = present[:10], present[10:]       # 앞 10장에서 고르고 뒤 10장에서 확인
    th = next((t for t in GRID
               if [r for r in dev if r["conf"] >= t] and all(r["iou"] >= 0.5 for r in dev if r["conf"] >= t)), None)
    print(f"\n개발 10장에서 고른 임계값 {th}")
    if th is not None:
        g = [r for r in hold if r["conf"] >= th]
        print(f"검증 10장  통과 {len(g)}장, 그중 IoU 0.5 이상 {sum(r['iou'] >= 0.5 for r in g)}장")


if __name__ == "__main__":
    main()
