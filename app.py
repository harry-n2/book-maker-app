"""Book Maker App ── AIリテラシー低い方向けの書籍生成 Web アプリ。"""

from __future__ import annotations

import os
import threading
import traceback
import uuid
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from generator import BookConfig, generate_book

BASE = Path(__file__).resolve().parent
JOBS = BASE / "jobs"
TEMPLATES = BASE / "templates"
STATIC = BASE / "static"

app = FastAPI(title="Book Maker", description="シンプルな書籍生成アプリ")
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

# ジョブ状態を保持するインメモリ辞書（プロセス内共有）
JOB_STATE: dict[str, dict] = {}


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return (TEMPLATES / "index.html").read_text(encoding="utf-8")


@app.post("/generate")
async def generate(
    theme: str = Form(...),
    target_layer: str = Form(...),
    author: str = Form(...),
    api_key: str = Form(...),
):
    if not theme.strip() or not author.strip() or not api_key.strip():
        raise HTTPException(status_code=400, detail="未入力の項目があります。")

    job_id = uuid.uuid4().hex[:8]
    job_dir = JOBS / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    cfg = BookConfig(
        theme=theme.strip(),
        target_layer=target_layer.strip(),
        author=author.strip(),
        api_key=api_key.strip(),
    )
    JOB_STATE[job_id] = {"status": "running", "progress": 0, "message": "開始しています..."}

    def runner():
        try:
            def progress(msg: str, pct: int) -> None:
                JOB_STATE[job_id]["progress"] = pct
                JOB_STATE[job_id]["message"] = msg

            result = generate_book(cfg, job_dir, progress)
            JOB_STATE[job_id].update({
                "status": "done",
                "progress": 100,
                "message": "完了しました。",
                "result": result,
            })
        except Exception as exc:  # noqa: BLE001
            JOB_STATE[job_id].update({
                "status": "error",
                "progress": JOB_STATE[job_id].get("progress", 0),
                "message": f"エラーが発生しました：{exc}",
                "trace": traceback.format_exc(),
            })

    threading.Thread(target=runner, daemon=True).start()
    return {"job_id": job_id}


@app.get("/status/{job_id}")
async def status(job_id: str) -> JSONResponse:
    state = JOB_STATE.get(job_id)
    if not state:
        return JSONResponse({"status": "not_found"}, status_code=404)
    payload = {
        "status": state["status"],
        "progress": state.get("progress", 0),
        "message": state.get("message", ""),
    }
    if state["status"] == "done":
        payload["result"] = state["result"]
    if state["status"] == "error":
        payload["message"] = state.get("message", "エラー")
    return JSONResponse(payload)


@app.get("/download/{job_id}/{filename}")
async def download(job_id: str, filename: str):
    if filename not in {"book_full.md", "book_full.docx", "outline.json"}:
        raise HTTPException(status_code=400, detail="不正なファイル名です。")
    fpath = JOBS / job_id / filename
    if not fpath.exists():
        raise HTTPException(status_code=404, detail="ファイルが見つかりません。")
    media_type = "application/octet-stream"
    if filename.endswith(".md"):
        media_type = "text/markdown; charset=utf-8"
    elif filename.endswith(".docx"):
        media_type = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    return FileResponse(str(fpath), media_type=media_type, filename=filename)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8765"))
    uvicorn.run("app:app", host="127.0.0.1", port=port, reload=False)
