# -*- coding: utf-8 -*-
"""12-6: 가중치 리비전을 고정해 Laya 서버를 띄운다.

laya 0.3.20 의 기본 서버(laya-serve)는 가중치를 리비전 지정 없이 내려받아,
Hugging Face 저장소가 바뀌면 다른 가중치로 돕니다. 이 스크립트는 정한 리비전을
로컬 폴더에 받아 두고, 그 폴더를 laya 의 Router 에 직접 연결합니다.

    pip install "laya[serve]==0.3.20"
    python ch12/laya_serve_pinned.py                       책 12-6 의 리비전(55cf4c4)
    python ch12/laya_serve_pinned.py --revision main       최신 가중치 (비교용)

서버는 127.0.0.1:8010 에서 Jev 와 같은 POST /v1/systemone 을 받습니다.
영어·다국어 체크포인트 두 개만 제공합니다(typed-decisions 는 제공하지 않음).
GET /pinned 로 패키지 버전, 가중치 리비전, 제공하는 체크포인트의 출처를 확인할 수 있습니다.
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

    served = {"english": (local, None), "multilingual": (local, "multilingual")}
    router = Router(models=served, device=a.device, preload=False)
    # Router(models=...) 는 기본 목록 위에 덮어쓴다. 남는 typed-decisions 는 리비전 없이
    # 원격에서 받히므로 목록에서 빼고, 고정한 두 체크포인트만 미리 불러온다.
    for name in list(router.models):
        if name not in served:
            del router.models[name]
    router.preload(list(served))
    app = create_app(router)
    info = {"laya": version("laya"), "repo": REPO, "revision": revision, "dir": os.path.abspath(local),
            "models": {name: f"{REPO}@{revision[:7]}" + (f"/{sub}" if sub else "")
                       for name, (_, sub) in served.items()}}

    @app.get("/pinned")
    def pinned():
        return {k: v for k, v in info.items() if k != "dir"}

    print(f"laya {info['laya']}  {REPO}@{revision[:7]}  -> http://{a.host}:{a.port}", flush=True)
    uvicorn.run(app, host=a.host, port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
