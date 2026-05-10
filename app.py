"""Book Maker App ── AIリテラシー低い方向けの書籍生成 Web アプリ。"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import traceback
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from generator import BookConfig, generate_book
from references import (
    Reference,
    analyze_image,
    extract_file,
    fetch_notebooklm,
    fetch_url,
)

BASE = Path(__file__).resolve().parent
JOBS = BASE / "jobs"
TEMPLATES = BASE / "templates"
STATIC = BASE / "static"

app = FastAPI(title="Book Maker", description="シンプルな書籍生成アプリ")
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

JOB_STATE: dict[str, dict] = {}

ALLOWED_FILE_EXT = {".pdf", ".docx", ".md", ".markdown", ".txt", ".csv", ".json", ".yml", ".yaml"}
ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
MAX_FILE_BYTES = 20 * 1024 * 1024  # 20MB / file
MAX_FILES_PER_KIND = 20            # ファイル・画像はそれぞれ最大20個まで


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return (TEMPLATES / "index.html").read_text(encoding="utf-8")


def _save_upload(upload: UploadFile, dest_dir: Path) -> Path:
    safe_name = Path(upload.filename or "upload").name
    dest = dest_dir / safe_name
    with dest.open("wb") as fp:
        shutil.copyfileobj(upload.file, fp)
    if dest.stat().st_size > MAX_FILE_BYTES:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=413, detail=f"{safe_name} は 20MB を超えています。")
    return dest


def _collect_references(
    job_dir: Path,
    api_key: str,
    urls: list[str],
    files: list[UploadFile],
    images: list[UploadFile],
    notebooklm_urls: list[str],
) -> list[Reference]:
    file_count = sum(1 for f in (files or []) if f and f.filename)
    image_count = sum(1 for f in (images or []) if f and f.filename)
    if file_count > MAX_FILES_PER_KIND:
        raise HTTPException(
            status_code=400,
            detail=f"添付ファイルは最大 {MAX_FILES_PER_KIND} 個までです（送信されたのは {file_count} 個）。",
        )
    if image_count > MAX_FILES_PER_KIND:
        raise HTTPException(
            status_code=400,
            detail=f"添付画像は最大 {MAX_FILES_PER_KIND} 個までです（送信されたのは {image_count} 個）。",
        )

    refs: list[Reference] = []
    refs_dir = job_dir / "references"
    refs_dir.mkdir(parents=True, exist_ok=True)

    for u in urls:
        u = (u or "").strip()
        if u:
            refs.append(fetch_url(u))

    for nb in notebooklm_urls:
        nb = (nb or "").strip()
        if nb:
            refs.append(fetch_notebooklm(nb))

    for f in files:
        if not f or not f.filename:
            continue
        ext = Path(f.filename).suffix.lower()
        if ext not in ALLOWED_FILE_EXT:
            refs.append({
                "label": f"file: {f.filename}",
                "kind": "file",
                "content": f"[未対応の拡張子：{ext}]",
            })
            continue
        saved = _save_upload(f, refs_dir)
        refs.append(extract_file(saved, original_name=f.filename))

    for img in images:
        if not img or not img.filename:
            continue
        ext = Path(img.filename).suffix.lower()
        if ext not in ALLOWED_IMAGE_EXT:
            refs.append({
                "label": f"image: {img.filename}",
                "kind": "image",
                "content": f"[未対応の画像拡張子：{ext}]",
            })
            continue
        saved = _save_upload(img, refs_dir)
        refs.append(analyze_image(saved, original_name=img.filename, api_key=api_key))

    return refs


@app.post("/generate")
async def generate(
    theme: str = Form(...),
    target_layer: str = Form(...),
    author: str = Form(...),
    api_key: str = Form(...),
    project_id: str = Form(""),
    project_name: str = Form(""),
    ref_urls: str = Form(""),
    notebooklm_urls: str = Form(""),
    files: list[UploadFile] = File(default=[]),
    images: list[UploadFile] = File(default=[]),
):
    if not theme.strip() or not author.strip() or not api_key.strip():
        raise HTTPException(status_code=400, detail="未入力の項目があります。")

    job_id = uuid.uuid4().hex[:8]
    job_dir = JOBS / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    url_list = [line.strip() for line in (ref_urls or "").splitlines() if line.strip()]
    nb_list = [line.strip() for line in (notebooklm_urls or "").splitlines() if line.strip()]

    JOB_STATE[job_id] = {
        "status": "running",
        "progress": 0,
        "message": "参照ソースを取り込んでいます...",
        "project_id": project_id.strip() or job_id,
        "project_name": project_name.strip() or theme[:30],
    }

    references = _collect_references(
        job_dir=job_dir,
        api_key=api_key.strip(),
        urls=url_list,
        files=files or [],
        images=images or [],
        notebooklm_urls=nb_list,
    )

    (job_dir / "references_index.json").write_text(
        json.dumps(
            [{"label": r["label"], "kind": r["kind"], "char_count": len(r["content"])} for r in references],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    cfg = BookConfig(
        theme=theme.strip(),
        target_layer=target_layer.strip(),
        author=author.strip(),
        api_key=api_key.strip(),
        references=references,
    )

    def runner() -> None:
        try:
            def progress(msg: str, pct: int) -> None:
                JOB_STATE[job_id]["progress"] = pct
                JOB_STATE[job_id]["message"] = msg

            result = generate_book(cfg, job_dir, progress)
            result["reference_count"] = len(references)
            JOB_STATE[job_id].update({
                "status": "done",
                "progress": 100,
                "message": "完了しました。",
                "result": result,
            })
        except Exception as exc:  # noqa: BLE001
            JOB_STATE[job_id].update({
                "status": "error",
                "message": f"エラーが発生しました：{exc}",
                "trace": traceback.format_exc(),
            })

    threading.Thread(target=runner, daemon=True).start()
    return {
        "job_id": job_id,
        "project_id": JOB_STATE[job_id]["project_id"],
        "reference_count": len(references),
    }


@app.get("/status/{job_id}")
async def status(job_id: str) -> JSONResponse:
    state = JOB_STATE.get(job_id)
    if not state:
        return JSONResponse({"status": "not_found"}, status_code=404)
    payload: dict[str, Any] = {
        "status": state["status"],
        "progress": state.get("progress", 0),
        "message": state.get("message", ""),
        "project_id": state.get("project_id"),
        "project_name": state.get("project_name"),
    }
    if state["status"] == "done":
        payload["result"] = state["result"]
    if state["status"] == "error":
        payload["message"] = state.get("message", "エラー")
    return JSONResponse(payload)


@app.get("/download/{job_id}/{filename}")
async def download(job_id: str, filename: str):
    if filename not in {"book_full.md", "book_full.docx", "outline.json", "references_index.json"}:
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
    elif filename.endswith(".json"):
        media_type = "application/json; charset=utf-8"
    return FileResponse(str(fpath), media_type=media_type, filename=filename)


@app.get("/notebooklm-export/{job_id}")
async def notebooklm_export(job_id: str):
    """NotebookLM 取り込み用の集約 Markdown を生成する。

    NotebookLM 公式 API は未公開のため、ユーザーがブラウザで NotebookLM の
    『+ ソースを追加』に貼り付けるための Markdown を返す。
    """
    job_dir = JOBS / job_id
    md_path = job_dir / "book_full.md"
    if not md_path.exists():
        raise HTTPException(status_code=404, detail="まだ書籍が完成していません。")
    refs_idx = job_dir / "references_index.json"
    refs_text = ""
    if refs_idx.exists():
        try:
            data = json.loads(refs_idx.read_text(encoding="utf-8"))
            refs_text = "\n## 参照ソース\n" + "\n".join(
                f"- ({r['kind']}) {r['label']}（{r['char_count']}字）" for r in data
            ) + "\n"
        except Exception:
            pass
    body = md_path.read_text(encoding="utf-8")
    out = (job_dir / "book_for_notebooklm.md")
    out.write_text(
        f"<!-- NotebookLM 取り込み用エクスポート -->\n\n{body}\n{refs_text}",
        encoding="utf-8",
    )
    return FileResponse(
        str(out),
        media_type="text/markdown; charset=utf-8",
        filename="book_for_notebooklm.md",
    )


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8765"))
    uvicorn.run("app:app", host="127.0.0.1", port=port, reload=False)
