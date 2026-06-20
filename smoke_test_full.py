"""全工程ライブ検証（実Gemini）。タイトル→章立て→本編→紹介文→docx までを通す。
キーは表示しない。実行: python smoke_test_full.py
"""
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path


def _load_key() -> str:
    k = os.environ.get("GEMINI_API_KEY", "").strip()
    if k:
        return k
    f = Path(__file__).with_name(".localkey")
    return f.read_text(encoding="utf-8").strip() if f.exists() else ""


def main() -> int:
    key = _load_key()
    if not key:
        print("NG: APIキー未設定")
        return 2

    from generator import (
        BookConfig,
        resolve_model,
        start_titles_job,
        generate_structure_for_review,
        start_writing,
    )

    job_dir = Path(__file__).with_name("jobs") / "_smoke_full"
    if job_dir.exists():
        shutil.rmtree(job_dir, ignore_errors=True)
    job_dir.mkdir(parents=True, exist_ok=True)

    cfg = BookConfig(
        theme="AIで副業を仕組み化して月10万円を安定させる実践ガイド",
        target_layer="副業1〜3年目の30代会社員（実績はあるが伸び悩んでいる方）",
        author="テスト著者",
        api_key=key,
        profile_author_bio="中小企業のWeb集客を10年支援。",
        profile_tone="落ち着いた実務家の口調。",
        profile_target_keywords=["副業", "AI活用", "仕組み化"],
    )
    print(f"使用モデル: {resolve_model(cfg.model)}")

    t0 = time.time()
    print("[1/3] タイトル10選 ...")
    cands = start_titles_job(cfg, job_dir)
    print(f"   -> {len(cands)} 件")

    print("[2/3] 章立て（採用index=0） ...")
    structure = generate_structure_for_review(cfg, job_dir, cands, 0)
    chs = structure.get("chapters", [])
    print(f"   -> 章数 {len(chs)} / title={structure.get('title')!r}")

    print("[3/3] 本編＋紹介文＋docx（時間がかかります） ...")
    def progress(msg: str, pct: int) -> None:
        print(f"   {pct:>3}% {msg}")
    result = start_writing(cfg, job_dir, structure, cands, 0, progress)

    md = job_dir / "book_full.md"
    docx = job_dir / "book_full.docx"
    desc = job_dir / "book_description.md"
    print("\n=== 成果物チェック ===")
    ok = True
    for label, p in [("book_full.md", md), ("book_full.docx", docx), ("book_description.md", desc)]:
        exists = p.exists()
        size = p.stat().st_size if exists else 0
        print(f"  {label}: {'OK' if exists and size > 0 else 'NG'} ({size} bytes)")
        ok = ok and exists and size > 0

    print(f"\n本文文字数: {result.get('char_count')} / 章数: {result.get('chapter_count')}")
    print(f"所要: {time.time()-t0:.1f}s")
    if md.exists():
        head = md.read_text(encoding="utf-8")[:300].replace("\n", " ")
        print(f"本文冒頭: {head}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
