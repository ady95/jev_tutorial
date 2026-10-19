# -*- coding: utf-8 -*-
"""12-6: 가중치 리비전을 고정해 Laya 서버를 띄운다.

laya 0.3.20 의 기본 서버(laya-serve)는 가중치를 리비전 지정 없이 내려받아,
Hugging Face 저장소가 바뀌면 다른 가중치로 돕니다. 이 스크립트는 정한 리비전을
로컬 폴더에 받아 두고, 그 폴더를 laya 의 Router 에 직접 연결합니다.

    pip install "laya[serve]==0.3.20"
    python ch12/laya_serve_pinned.py                       책 12-6 의 리비전(55cf4c4)
    python ch12/laya_serve_pinned.py --revision main       최신 가중치 (비교용)

서버는 127.0.0.1:8010 에서 Jev 와 같은 POST /v1/systemone 을 받습니다.
GET /pinned 로 지금 돌고 있는 패키지 버전과 가중치 리비전을 확인할 수 있습니다.
"""
import argparse
import os
from importlib.metadata import version

BOOK_REVISION = "55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851"   # 책 12-6 의 측정 (2026-09-25)
REPO = "convaiinnovations/laya"
FILES = ["rl_agent_config.json", "model.safetensors", "tokenizer/*", "encoder/*"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--revision", default=BOOK_REVISION, help="가중치 커밋 (기본: 책 12-6 의 리비전)")
    ap.add_argument("--dir", default=None, help="가중치를 받을 폴더 (기본: laya_weights_<리비전 앞 7자리>)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8010)
    ap.add_argument("--device", default=os.environ.get("LAYA_DEVICE", "cpu"))
    a = ap.parse_args()

    from huggingface_hub import HfApi, snapshot_download

    revision = a.revision
    if len(revision) != 40:                                  # main 같은 이름은 실제 커밋으로 바꿔 기록한다
        revision = HfApi().model_info(REPO, revision=revision).sha
    local = a.dir or f"laya_weights_{revision[:7]}"
    # 영어 체크포인트(저장소 루트)와 다국어 체크포인트(multilingual/)만 받는다
    patterns = FILES + ["multilingual/" + f for f in FILES]
    snapshot_download(REPO, revision=revision, allow_patterns=patterns, local_dir=local)

    import uvicorn
    from laya.router import Router
    from laya.serve import create_app

    router = Router(models={"english": (local, None), "multilingual": (local, "multilingual")},
                    device=a.device, preload=True)
    app = create_app(router)
    info = {"laya": version("laya"), "repo": REPO, "revision": revision, "dir": os.path.abspath(local)}

    @app.get("/pinned")
    def pinned():
        return {k: v for k, v in info.items() if k != "dir"}

    print(f"laya {info['laya']}  {REPO}@{revision[:7]}  -> http://{a.host}:{a.port}", flush=True)
    uvicorn.run(app, host=a.host, port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
