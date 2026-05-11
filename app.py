"""Book Maker App ── 3段階UX（タイトル10選 → 章立てレビュー → 本編）。"""

from __future__ import annotations

import json
import os
import shutil
import threading
import traceback
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from generator import (
    BookConfig,
    generate_structure_bestseller,
    generate_structure_for_review,
    modify_structure,
    regenerate_titles_bestseller,
    start_titles_job,
    start_writing,
)
from references import (
    Reference,
    analyze_image,
    extract_file,
    fetch_notebooklm,
    fetch_url,
)
import _resource

BASE = _resource.resource_root()
JOBS = _resource.jobs_dir()
TEMPLATES = _resource.resource("templates")
STATIC = _resource.resource("static")

app = FastAPI(title="Book Maker", description="3段階UX 書籍生成アプリ")
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

JOB_STATE: dict[str, dict] = {}

ALLOWED_FILE_EXT = {".pdf", ".docx", ".md", ".markdown", ".txt", ".csv", ".json", ".yml", ".yaml"}
ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_FILES_PER_KIND = 10
MAX_REGEN_PER_STAGE = 3


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
            refs.append({"label": f"file: {f.filename}", "kind": "file", "content": f"[未対応の拡張子：{ext}]"})
            continue
        saved = _save_upload(f, refs_dir)
        refs.append(extract_file(saved, original_name=f.filename))

    for img in images:
        if not img or not img.filename:
            continue
        ext = Path(img.filename).suffix.lower()
        if ext not in ALLOWED_IMAGE_EXT:
            refs.append({"label": f"image: {img.filename}", "kind": "image", "content": f"[未対応の画像拡張子：{ext}]"})
            continue
        saved = _save_upload(img, refs_dir)
        refs.append(analyze_image(saved, original_name=img.filename, api_key=api_key))

    return refs


def _cfg_from_state(state: dict) -> BookConfig:
    cfg_data = state.get("cfg") or {}
    return BookConfig(
        theme=cfg_data.get("theme", ""),
        target_layer=cfg_data.get("target_layer", ""),
        author=cfg_data.get("author", ""),
        api_key=cfg_data.get("api_key", ""),
        references=cfg_data.get("references", []),
    )


# ---------------------------------------------------------------------------
# Step 1: タイトル10選を生成（同期・30〜45秒）
# ---------------------------------------------------------------------------


@app.post("/generate-titles")
async def generate_titles_endpoint(
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

    try:
        candidates = start_titles_job(cfg, job_dir)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"タイトル生成に失敗しました：{exc}")

    JOB_STATE[job_id] = {
        "status": "title_picked",
        "progress": 0,
        "message": "タイトルを選んでください。",
        "project_id": project_id.strip() or job_id,
        "project_name": project_name.strip() or theme[:30],
        "candidates": candidates,
        "cfg": {
            "theme": cfg.theme,
            "target_layer": cfg.target_layer,
            "author": cfg.author,
            "api_key": cfg.api_key,
            "references": cfg.references,
        },
        "reference_count": len(references),
        "titles_regen_count": 0,
        "structure_regen_count": 0,
        "structure_modify_count": 0,
        "current_structure": None,
        "adopted_index": None,
    }
    return {
        "job_id": job_id,
        "candidates": candidates,
        "reference_count": len(references),
        "titles_regen_count": 0,
        "max_regen_per_stage": MAX_REGEN_PER_STAGE,
    }


# ---------------------------------------------------------------------------
# Step 1-b: タイトル10選を「ベストセラー版」で再生成
# ---------------------------------------------------------------------------


@app.post("/regenerate-titles/{job_id}")
async def regenerate_titles_endpoint(job_id: str):
    state = JOB_STATE.get(job_id)
    if not state:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません。最初からやり直してください。")
    if state.get("status") != "title_picked":
        raise HTTPException(
            status_code=409,
            detail=f"現在のステータス（{state.get('status')}）からはタイトル再生成できません。",
        )
    if state.get("titles_regen_count", 0) >= MAX_REGEN_PER_STAGE:
        raise HTTPException(
            status_code=429,
            detail=f"タイトル再生成は {MAX_REGEN_PER_STAGE} 回までです。1つ選んで先に進んでください。",
        )

    cfg = _cfg_from_state(state)
    prev_candidates = state.get("candidates", [])
    try:
        new_candidates = regenerate_titles_bestseller(cfg, prev_candidates)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"タイトル再生成に失敗しました：{exc}")

    state["candidates"] = new_candidates
    state["titles_regen_count"] = state.get("titles_regen_count", 0) + 1
    state["message"] = "ベストセラー版で再生成しました。お好きな1案をお選びください。"

    job_dir = JOBS / job_id
    (job_dir / "title_candidates.json").write_text(
        json.dumps(new_candidates, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {
        "job_id": job_id,
        "candidates": new_candidates,
        "titles_regen_count": state["titles_regen_count"],
        "max_regen_per_stage": MAX_REGEN_PER_STAGE,
    }


# ---------------------------------------------------------------------------
# Step 2: タイトル確定 → 章立て生成（非同期・ユーザー確認待ち）
# ---------------------------------------------------------------------------


@app.post("/confirm-title/{job_id}")
async def confirm_title_endpoint(job_id: str, adopted_index: int = Form(...)):
    state = JOB_STATE.get(job_id)
    if not state:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません。最初からやり直してください。")
    if state.get("status") != "title_picked":
        raise HTTPException(
            status_code=409,
            detail=f"現在のステータス（{state.get('status')}）からは章立て生成に進めません。",
        )
    candidates = state.get("candidates") or []
    if not 0 <= adopted_index < len(candidates):
        raise HTTPException(status_code=400, detail="採用 index が範囲外です。")

    state["adopted_index"] = adopted_index
    state["status"] = "generating_structure"
    state["progress"] = 10
    state["message"] = "章立て（章構成）を生成中..."

    cfg = _cfg_from_state(state)
    job_dir = JOBS / job_id

    def runner() -> None:
        try:
            structure = generate_structure_for_review(cfg, job_dir, candidates, adopted_index)
            JOB_STATE[job_id].update({
                "status": "structure_review",
                "progress": 0,
                "message": "章立てが整いました。確認してください。",
                "current_structure": structure,
            })
        except Exception as exc:  # noqa: BLE001
            JOB_STATE[job_id].update({
                "status": "error",
                "message": f"章立て生成に失敗しました：{exc}",
                "trace": traceback.format_exc(),
            })

    threading.Thread(target=runner, daemon=True).start()
    return {"job_id": job_id, "adopted_index": adopted_index}


# ---------------------------------------------------------------------------
# Step 2-b: 章立てをベストセラー版で再生成（非同期）
# ---------------------------------------------------------------------------


@app.post("/regenerate-structure/{job_id}")
async def regenerate_structure_endpoint(job_id: str):
    state = JOB_STATE.get(job_id)
    if not state:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません。")
    if state.get("status") != "structure_review":
        raise HTTPException(
            status_code=409,
            detail=f"現在のステータス（{state.get('status')}）からは章立て再生成できません。",
        )
    if state.get("structure_regen_count", 0) >= MAX_REGEN_PER_STAGE:
        raise HTTPException(
            status_code=429,
            detail=f"章立て再生成は {MAX_REGEN_PER_STAGE} 回までです。承認して本編に進んでください。",
        )

    candidates = state.get("candidates") or []
    adopted_index = state.get("adopted_index")
    if adopted_index is None or not 0 <= adopted_index < len(candidates):
        raise HTTPException(status_code=400, detail="採用タイトルが特定できません。")
    adopted = candidates[adopted_index]
    adopted_title = adopted.get("title", "")
    adopted_subtitle = adopted.get("subtitle", "")
    prev_structure = state.get("current_structure") or {}

    cfg = _cfg_from_state(state)
    job_dir = JOBS / job_id

    state["status"] = "regenerating_structure"
    state["message"] = "ベストセラー強化版の章立てを生成中..."

    def runner() -> None:
        try:
            new_structure = generate_structure_bestseller(cfg, adopted_title, adopted_subtitle, prev_structure)
            (job_dir / "structure.json").write_text(
                json.dumps(new_structure, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            JOB_STATE[job_id].update({
                "status": "structure_review",
                "message": "ベストセラー版で章立てを再生成しました。確認してください。",
                "current_structure": new_structure,
                "structure_regen_count": JOB_STATE[job_id].get("structure_regen_count", 0) + 1,
            })
        except Exception as exc:  # noqa: BLE001
            JOB_STATE[job_id].update({
                "status": "structure_review",
                "message": f"章立て再生成に失敗しました：{exc}（前回の章立てを保持しています）",
                "trace": traceback.format_exc(),
            })

    threading.Thread(target=runner, daemon=True).start()
    return {
        "job_id": job_id,
        "structure_regen_count": state.get("structure_regen_count", 0) + 1,
        "max_regen_per_stage": MAX_REGEN_PER_STAGE,
    }


# ---------------------------------------------------------------------------
# Step 2-c: 章立ての部分修正（非同期）
# ---------------------------------------------------------------------------


@app.post("/modify-structure/{job_id}")
async def modify_structure_endpoint(job_id: str, user_instruction: str = Form(...)):
    state = JOB_STATE.get(job_id)
    if not state:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません。")
    if state.get("status") != "structure_review":
        raise HTTPException(
            status_code=409,
            detail=f"現在のステータス（{state.get('status')}）からは部分修正できません。",
        )
    if state.get("structure_modify_count", 0) >= MAX_REGEN_PER_STAGE:
        raise HTTPException(
            status_code=429,
            detail=f"部分修正は {MAX_REGEN_PER_STAGE} 回までです。承認して本編に進んでください。",
        )
    if not user_instruction or not user_instruction.strip():
        raise HTTPException(status_code=400, detail="修正指示が空です。")

    candidates = state.get("candidates") or []
    adopted_index = state.get("adopted_index")
    if adopted_index is None or not 0 <= adopted_index < len(candidates):
        raise HTTPException(status_code=400, detail="採用タイトルが特定できません。")
    adopted = candidates[adopted_index]
    adopted_title = adopted.get("title", "")
    adopted_subtitle = adopted.get("subtitle", "")
    current_structure = state.get("current_structure") or {}

    cfg = _cfg_from_state(state)
    job_dir = JOBS / job_id

    state["status"] = "modifying_structure"
    state["message"] = "章立てを部分修正中..."

    def runner() -> None:
        try:
            new_structure = modify_structure(cfg, current_structure, user_instruction, adopted_title, adopted_subtitle)
            (job_dir / "structure.json").write_text(
                json.dumps(new_structure, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            JOB_STATE[job_id].update({
                "status": "structure_review",
                "message": "章立てを修正しました。確認してください。",
                "current_structure": new_structure,
                "structure_modify_count": JOB_STATE[job_id].get("structure_modify_count", 0) + 1,
            })
        except Exception as exc:  # noqa: BLE001
            JOB_STATE[job_id].update({
                "status": "structure_review",
                "message": f"部分修正に失敗しました：{exc}（前回の章立てを保持しています）",
                "trace": traceback.format_exc(),
            })

    threading.Thread(target=runner, daemon=True).start()
    return {
        "job_id": job_id,
        "structure_modify_count": state.get("structure_modify_count", 0) + 1,
        "max_regen_per_stage": MAX_REGEN_PER_STAGE,
    }


# ---------------------------------------------------------------------------
# Step 3: 章立て承認 → 本編生成（バックグラウンド）
# ---------------------------------------------------------------------------


@app.post("/approve-structure/{job_id}")
async def approve_structure_endpoint(job_id: str):
    state = JOB_STATE.get(job_id)
    if not state:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません。")
    if state.get("status") != "structure_review":
        raise HTTPException(
            status_code=409,
            detail=f"現在のステータス（{state.get('status')}）からは本編生成に進めません。章立てレビュー画面から承認してください。",
        )
    structure = state.get("current_structure")
    if not structure:
        raise HTTPException(status_code=400, detail="章立てが未生成です。")
    candidates = state.get("candidates") or []
    adopted_index = state.get("adopted_index")
    if adopted_index is None or not 0 <= adopted_index < len(candidates):
        raise HTTPException(status_code=400, detail="採用タイトルが特定できません。")

    cfg = _cfg_from_state(state)
    job_dir = JOBS / job_id
    state.update({"status": "running", "progress": 12, "message": "本編の執筆を開始します..."})

    def runner() -> None:
        try:
            def progress(msg: str, pct: int) -> None:
                JOB_STATE[job_id]["progress"] = pct
                JOB_STATE[job_id]["message"] = msg

            result = start_writing(cfg, job_dir, structure, candidates, adopted_index, progress)
            result["reference_count"] = state.get("reference_count", 0)
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
    return {"job_id": job_id}


# ---------------------------------------------------------------------------
# Status / Download
# ---------------------------------------------------------------------------


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
        "titles_regen_count": state.get("titles_regen_count", 0),
        "structure_regen_count": state.get("structure_regen_count", 0),
        "structure_modify_count": state.get("structure_modify_count", 0),
        "max_regen_per_stage": MAX_REGEN_PER_STAGE,
        "adopted_index": state.get("adopted_index"),
    }
    if state["status"] in ("title_picked", "generating_structure", "structure_review", "regenerating_structure", "modifying_structure", "running"):
        payload["candidates"] = state.get("candidates", [])
    if state["status"] in ("structure_review", "regenerating_structure", "modifying_structure", "running"):
        payload["structure"] = state.get("current_structure")
    if state["status"] == "done":
        payload["result"] = state["result"]
    if state["status"] == "error":
        payload["message"] = state.get("message", "エラー")
    return JSONResponse(payload)


@app.get("/download/{job_id}/{filename}")
async def download(job_id: str, filename: str):
    allowed = {
        "book_full.md",
        "book_full.docx",
        "title_candidates.md",
        "book_description.md",
        "structure.json",
        "references_index.json",
    }
    if filename not in allowed:
        raise HTTPException(status_code=400, detail="不正なファイル名です。")
    fpath = JOBS / job_id / filename
    if not fpath.exists():
        raise HTTPException(status_code=404, detail="ファイルが見つかりません。")
    media_type = "application/octet-stream"
    if filename.endswith(".md"):
        media_type = "text/markdown; charset=utf-8"
    elif filename.endswith(".docx"):
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif filename.endswith(".json"):
        media_type = "application/json; charset=utf-8"
    return FileResponse(str(fpath), media_type=media_type, filename=filename)


@app.get("/notebooklm-export/{job_id}")
async def notebooklm_export(job_id: str):
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
    out = job_dir / "book_for_notebooklm.md"
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
