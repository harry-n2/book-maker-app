"""Book Maker App ── 3段階UX（タイトル10選 → 章立てレビュー → 本編）。"""

from __future__ import annotations

import json
import os
import re
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
    build_write_plan,
    clean_public_manuscript,
    finalize_book,
    generate_description,
    generate_promotion,
    generate_structure_bestseller,
    generate_structure_for_review,
    regenerate_titles_bestseller,
    start_titles_job,
    start_writing,
    write_one_section,
)
from references import (
    Reference,
    analyze_image,
    extract_file,
    fetch_notebooklm,
    fetch_pasted_text,
    fetch_url,
)
import _resource
import store

BASE = _resource.resource_root()
JOBS = _resource.jobs_dir()
TEMPLATES = _resource.resource("templates")
STATIC = _resource.resource("static")

app = FastAPI(title="Book Maker", description="3段階UX 書籍生成アプリ")
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

# 永続化: ローカル=SQLite / 本番=DATABASE_URL があれば Postgres（$0・有料課金なし）。
# プロセス再起動・サーバーレス再実行をまたいでジョブ状態が残る。APIキーはDBに保存しない（store.py）。
JOB_STATE = store.PersistentJobState()

ALLOWED_FILE_EXT = {".pdf", ".docx", ".md", ".markdown", ".txt", ".csv", ".json", ".yml", ".yaml"}
ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_FILES_PER_KIND = 10
MAX_REGEN_PER_STAGE = 3


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    html = (TEMPLATES / "index.html").read_text(encoding="utf-8")
    # 本番永続化(無料Postgres/DATABASE_URL)が未設定なら警告を表示（A案）。未設定でもアプリは動作する。
    if not os.environ.get("DATABASE_URL"):
        notice = (
            '<div class="persistence-warning" role="status">'
            "⚠ 本番の永続化は未設定です。ブラウザを閉じたり時間が経つと、進行中ジョブが消える場合があります。"
            "無料の Neon などの DATABASE_URL を設定すると永続化できます（有料契約は不要）。"
            "</div>"
        )
        html = html.replace("<!--PERSISTENCE_NOTICE-->", notice)
    else:
        html = html.replace("<!--PERSISTENCE_NOTICE-->", "")
    return html


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
    pasted_texts: list[str] | None = None,
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

    for i, pt in enumerate(pasted_texts or [], 1):
        if pt and pt.strip():
            refs.append(fetch_pasted_text(pt, label=f"直貼りテキスト {i}"))

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
        profile_name=cfg_data.get("profile_name", ""),
        profile_author_bio=cfg_data.get("profile_author_bio", ""),
        profile_tone=cfg_data.get("profile_tone", ""),
        profile_target_keywords=cfg_data.get("profile_target_keywords", []),
        profile_failure_bank=cfg_data.get("profile_failure_bank", []),
        profile_voice_types=cfg_data.get("profile_voice_types", []),
    )


# ---------------------------------------------------------------------------
# Step 1: タイトル10選を生成（同期・30〜45秒）
# ---------------------------------------------------------------------------


def _refs_payload(refs: list[Reference]) -> list[dict]:
    """フロントに返す参照ソース概要（label/kind/char_count/warning）。"""
    return [
        {
            "label": r["label"],
            "kind": r["kind"],
            "char_count": len(r.get("content", "") or ""),
            "warning": r.get("warning"),
            "preview": (r.get("content", "") or "").strip()[:200],
        }
        for r in refs
    ]


def _split_profile_lines(value: str) -> list[str]:
    return [line.strip() for line in (value or "").splitlines() if line.strip()]


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
    pasted_text: str = Form(""),
    profile_name: str = Form(""),
    profile_author_bio: str = Form(""),
    profile_tone: str = Form(""),
    profile_target_keywords: str = Form(""),
    profile_failure_bank: str = Form(""),
    profile_voice_types: str = Form(""),
    files: list[UploadFile] = File(default=[]),
    images: list[UploadFile] = File(default=[]),
):
    """v1.2: 参照素材の取り込みだけ実行し、タイトル生成は /confirm-references で行う。

    取り込み結果（warning 含む）をフロントに返し、ユーザーがプレビュー画面で確認・了承
    してからタイトル生成に進ませる（短すぎ・取得失敗を見逃さない設計）。
    """
    if not theme.strip() or not author.strip() or not api_key.strip():
        raise HTTPException(status_code=400, detail="未入力の項目があります。")

    job_id = uuid.uuid4().hex[:8]
    job_dir = JOBS / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    url_list = [line.strip() for line in (ref_urls or "").splitlines() if line.strip()]
    nb_list = [line.strip() for line in (notebooklm_urls or "").splitlines() if line.strip()]
    # 直貼りテキストは「---」で複数ソース区切り（先頭の --- は除外）
    pasted_list: list[str] = []
    if pasted_text and pasted_text.strip():
        chunks = re.split(r"(?m)^---+\s*$", pasted_text)
        for ch in chunks:
            s = ch.strip()
            if s:
                pasted_list.append(s)

    references = _collect_references(
        job_dir=job_dir,
        api_key=api_key.strip(),
        urls=url_list,
        files=files or [],
        images=images or [],
        notebooklm_urls=nb_list,
        pasted_texts=pasted_list,
    )
    (job_dir / "references_index.json").write_text(
        json.dumps(
            [
                {
                    "label": r["label"],
                    "kind": r["kind"],
                    "char_count": len(r.get("content", "") or ""),
                    "warning": r.get("warning"),
                }
                for r in references
            ],
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
        profile_name=profile_name.strip() or author.strip(),
        profile_author_bio=profile_author_bio.strip(),
        profile_tone=profile_tone.strip(),
        profile_target_keywords=_split_profile_lines(profile_target_keywords),
        profile_failure_bank=_split_profile_lines(profile_failure_bank),
        profile_voice_types=_split_profile_lines(profile_voice_types),
    )

    has_warning = any(r.get("warning") for r in references)
    JOB_STATE[job_id] = {
        "status": "references_review",
        "progress": 0,
        "message": "参照素材の取り込みが完了しました。確認してください。",
        "project_id": project_id.strip() or job_id,
        "project_name": project_name.strip() or theme[:30],
        "candidates": [],
        "cfg": {
            "theme": cfg.theme,
            "target_layer": cfg.target_layer,
            "author": cfg.author,
            "api_key": cfg.api_key,
            "references": cfg.references,
            "profile_name": cfg.profile_name,
            "profile_author_bio": cfg.profile_author_bio,
            "profile_tone": cfg.profile_tone,
            "profile_target_keywords": cfg.profile_target_keywords,
            "profile_failure_bank": cfg.profile_failure_bank,
            "profile_voice_types": cfg.profile_voice_types,
        },
        "reference_count": len(references),
        "references_payload": _refs_payload(references),
        "references_has_warning": has_warning,
        "titles_regen_count": 0,
        "structure_regen_count": 0,
        "current_structure": None,
        "adopted_index": None,
    }
    return {
        "job_id": job_id,
        "status": "references_review",
        "references": _refs_payload(references),
        "reference_count": len(references),
        "has_warning": has_warning,
        "max_regen_per_stage": MAX_REGEN_PER_STAGE,
    }


@app.post("/confirm-references/{job_id}")
async def confirm_references_endpoint(job_id: str):
    """参照素材プレビュー画面で「進む」を押したらタイトル10選を生成する。"""
    state = JOB_STATE.get(job_id)
    if not state:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません。最初からやり直してください。")
    if state.get("status") != "references_review":
        raise HTTPException(
            status_code=409,
            detail=f"現在のステータス（{state.get('status')}）からはタイトル生成に進めません。",
        )

    cfg = _cfg_from_state(state)
    job_dir = JOBS / job_id
    try:
        candidates = start_titles_job(cfg, job_dir)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"タイトル生成に失敗しました：{exc}")

    state.update({
        "status": "title_picked",
        "candidates": candidates,
        "message": "タイトルを選んでください。",
    })
    return {
        "job_id": job_id,
        "candidates": candidates,
        "reference_count": state.get("reference_count", 0),
        "titles_regen_count": state.get("titles_regen_count", 0),
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

    # サーバーレス対応: バックグラウンドスレッドを使わず、状態のみ進める。
    # 実際の章立て生成は /advance（クライアントのポーリングが駆動）で1工程として行う。
    state.update({
        "adopted_index": adopted_index,
        "status": "generating_structure",
        "progress": 10,
        "message": "章立て（章構成）を生成中...",
    })
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
    # サーバーレス対応: スレッドを使わず状態のみ進める。再生成は /advance が1工程として実行。
    state.update({
        "status": "regenerating_structure",
        "message": "ベストセラー強化版の章立てを生成中...",
    })
    return {
        "job_id": job_id,
        "structure_regen_count": state.get("structure_regen_count", 0) + 1,
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

    # サーバーレス対応: 本編は「1工程ずつ」進める。実生成は /advance（ポーリング駆動）で実行。
    plan = build_write_plan(structure)
    state.update({
        "status": "running",
        "progress": 12,
        "message": "本編の執筆を開始します...",
        "write_plan": plan,
        "write_cursor": 0,
    })
    return {"job_id": job_id}


# ---------------------------------------------------------------------------
# Status / Download
# ---------------------------------------------------------------------------


def _status_payload(state: dict) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": state["status"],
        "progress": state.get("progress", 0),
        "message": state.get("message", ""),
        "project_id": state.get("project_id"),
        "project_name": state.get("project_name"),
        "titles_regen_count": state.get("titles_regen_count", 0),
        "structure_regen_count": state.get("structure_regen_count", 0),
        "max_regen_per_stage": MAX_REGEN_PER_STAGE,
        "adopted_index": state.get("adopted_index"),
    }
    if state["status"] == "references_review":
        payload["references"] = state.get("references_payload", [])
        payload["has_warning"] = state.get("references_has_warning", False)
    if state["status"] in ("title_picked", "generating_structure", "structure_review", "regenerating_structure", "running"):
        payload["candidates"] = state.get("candidates", [])
    if state["status"] in ("structure_review", "regenerating_structure", "running"):
        payload["structure"] = state.get("current_structure")
    if state["status"] == "done":
        payload["result"] = state.get("result")
    if state["status"] == "error":
        payload["message"] = state.get("message", "エラー")
    return payload


@app.get("/status/{job_id}")
async def status(job_id: str) -> JSONResponse:
    state = JOB_STATE.get(job_id)
    if not state:
        return JSONResponse({"status": "not_found"}, status_code=404)
    return JSONResponse(_status_payload(state))


def _advance_one_write_step(job_id: str, state: dict, cfg: BookConfig, job_dir: Path) -> None:
    """status=running のとき write_plan を1工程だけ進める（サーバーレスで完走するための分割実行）。"""
    structure = state.get("current_structure") or {}
    plan = state.get("write_plan") or []
    cursor = state.get("write_cursor", 0)
    if cursor >= len(plan):
        return
    step = plan[cursor]
    kind = step.get("kind")
    candidates = state.get("candidates") or []
    adopted_index = state.get("adopted_index")
    total = max(1, len(plan))

    if kind == "section":
        write_one_section(cfg, job_dir, structure, structure.get("title", ""), step)
        msg = f"{step.get('label', '')}を作成しました"
    elif kind == "promotion":
        promo = clean_public_manuscript(generate_promotion(cfg, structure))
        (job_dir / "manuscript").mkdir(parents=True, exist_ok=True)
        (job_dir / "manuscript" / "98_promotion.md").write_text(promo, encoding="utf-8")
        msg = "巻末の宣伝セクションを作成しました"
    elif kind == "description":
        desc = clean_public_manuscript(generate_description(cfg, structure))
        (job_dir / "book_description.md").write_text(desc, encoding="utf-8")
        msg = "Kindle紹介文を作成しました"
    elif kind == "finalize":
        result = finalize_book(cfg, job_dir, structure, candidates, adopted_index)
        result["reference_count"] = state.get("reference_count", 0)
        state.update({
            "status": "done", "progress": 100, "message": "完了しました。",
            "result": result, "write_cursor": cursor + 1,
        })
        return
    else:
        state.update({"write_cursor": cursor + 1})
        return

    new_cursor = cursor + 1
    progress = min(95, 12 + int(new_cursor / total * 80))
    state.update({"write_cursor": new_cursor, "progress": progress, "message": msg})


@app.post("/advance/{job_id}")
async def advance_endpoint(job_id: str) -> JSONResponse:
    """ポーリングが駆動するワーカー。1呼び出しにつき1工程だけ実行し最新状態を返す。

    バックグラウンドスレッドを使わないため、Vercel等のサーバーレスでも多段ジョブが完走する。
    """
    state = JOB_STATE.get(job_id)
    if not state:
        return JSONResponse({"status": "not_found"}, status_code=404)
    st = state.get("status")
    cfg = _cfg_from_state(state)
    job_dir = JOBS / job_id
    candidates = state.get("candidates") or []
    adopted_index = state.get("adopted_index")
    try:
        if st == "generating_structure":
            structure = generate_structure_for_review(cfg, job_dir, candidates, adopted_index)
            state.update({
                "status": "structure_review", "progress": 0,
                "message": "章立てが整いました。確認してください。",
                "current_structure": structure,
            })
        elif st == "regenerating_structure":
            adopted = candidates[adopted_index] if (adopted_index is not None and 0 <= adopted_index < len(candidates)) else {}
            prev_structure = state.get("current_structure") or {}
            new_structure = generate_structure_bestseller(
                cfg, adopted.get("title", ""), adopted.get("subtitle", ""), prev_structure
            )
            (job_dir / "structure.json").write_text(
                json.dumps(new_structure, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            state.update({
                "status": "structure_review",
                "message": "ベストセラー版で章立てを再生成しました。確認してください。",
                "current_structure": new_structure,
                "structure_regen_count": state.get("structure_regen_count", 0) + 1,
            })
        elif st == "running":
            _advance_one_write_step(job_id, state, cfg, job_dir)
        # それ以外（references_review / title_picked / structure_review / done / error）は no-op。
    except Exception as exc:  # noqa: BLE001
        state.update({
            "status": "error",
            "message": f"生成に失敗しました：{exc}",
            "trace": traceback.format_exc(),
        })

    fresh = JOB_STATE.get(job_id) or {"status": "error", "message": "状態取得に失敗しました。"}
    return JSONResponse(_status_payload(fresh))


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

