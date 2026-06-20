"""残り3工程（おわりに・巻末宣伝・Kindle紹介文）だけを補完し、最終 md/docx まで作る。
既存の jobs/_smoke_full の structure.json と manuscript/ を利用。API呼び出しは3回だけ。
キーは表示しない。実行: python smoke_finish_tail.py
"""
from __future__ import annotations

import json
import os
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
        BookConfig, resolve_model, clean_public_manuscript,
        generate_chapter, generate_promotion, generate_description,
        build_merged_md, convert_to_docx,
    )

    jd = Path(__file__).with_name("jobs") / "_smoke_full"
    structure = json.loads((jd / "structure.json").read_text(encoding="utf-8"))
    man = jd / "manuscript"
    title = structure.get("title", "")
    subtitle = structure.get("subtitle", "")
    outro = structure.get("outro", {})

    cfg = BookConfig(
        theme="AIで副業を仕組み化して月10万円を安定させる実践ガイド",
        target_layer="副業1〜3年目の30代会社員（実績はあるが伸び悩んでいる方）",
        author="テスト著者", api_key=key,
        profile_author_bio="中小企業のWeb集客を10年支援。",
        profile_tone="落ち着いた実務家の口調。",
        profile_target_keywords=["副業", "AI活用", "仕組み化"],
    )
    print(f"使用モデル: {resolve_model(cfg.model)}")

    # 1) おわりに
    if not outro.get("sections"):
        outro["sections"] = [{"h2": "次の行動", "summary": outro.get("key_message", ""), "subsections": []}]
    print("[1/3] おわりに ...")
    body = clean_public_manuscript(generate_chapter(cfg, outro, 99, title, "おわりに"))
    (man / f"{outro.get('id','99_conclusion')}.md").write_text(body, encoding="utf-8")

    # 2) 巻末宣伝
    print("[2/3] 巻末宣伝 ...")
    promo = clean_public_manuscript(generate_promotion(cfg, structure))
    (man / "98_promotion.md").write_text(promo, encoding="utf-8")

    # 3) Kindle紹介文
    print("[3/3] Kindle紹介文 ...")
    desc = clean_public_manuscript(generate_description(cfg, structure))
    (jd / "book_description.md").write_text(desc, encoding="utf-8")

    # 統合 + docx
    merged = build_merged_md(title, subtitle, cfg.author, man, structure)
    mp = jd / "book_full.md"; mp.write_text(merged, encoding="utf-8")
    dp = jd / "book_full.docx"; convert_to_docx(mp, dp)

    print("\n=== 成果物 ===")
    import zipfile
    for label, p in [("book_full.md", mp), ("book_full.docx", dp), ("book_description.md", jd / "book_description.md")]:
        print(f"  {label}: {'OK' if p.exists() and p.stat().st_size>0 else 'NG'} ({p.stat().st_size if p.exists() else 0} bytes)")
    print("  DOCXはWord(zip)妥当:", zipfile.is_zipfile(dp))
    print(f"\n統合本文: {len(merged)} chars")
    print("おわりに冒頭:", body[:120].replace("\n", " "))
    print("紹介文冒頭:", desc[:160].replace("\n", " "))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
