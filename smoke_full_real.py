"""実APIで1冊フル生成（一気通貫・再開可能）。工程別モデルで無料枠日次上限を分散。キーは非表示。
途中でクォータに当たって再実行しても、保存済み工程はスキップして続きから完走する。
"""
from __future__ import annotations
import json, os, time
from pathlib import Path


def _key() -> str:
    k = os.environ.get("GEMINI_API_KEY", "").strip()
    if k:
        return k
    f = Path(__file__).with_name(".localkey")
    return f.read_text(encoding="utf-8").strip() if f.exists() else ""


def main() -> int:
    key = _key()
    if not key:
        print("NG: APIキー未設定"); return 2
    import generator as g

    jd = Path(__file__).with_name("jobs") / "_full_real2"
    jd.mkdir(parents=True, exist_ok=True)
    (jd / "manuscript").mkdir(parents=True, exist_ok=True)
    cfg = g.BookConfig(
        theme="AIで副業を仕組み化して月10万円を安定させる実践ガイド",
        target_layer="副業1〜3年目の30代会社員（実績はあるが伸び悩んでいる方）",
        author="テスト著者", api_key=key,
        profile_author_bio="中小企業のWeb集客を10年支援。", profile_tone="落ち着いた実務家の口調。",
        profile_target_keywords=["副業", "AI活用", "仕組み化"],
    )
    print("工程別モデル:",
          "TITLES=", g._step_model("TITLES", cfg), "STRUCTURE=", g._step_model("STRUCTURE", cfg),
          "CHAPTER=", g._step_model("CHAPTER", cfg), "OUTRO=", g._step_model("OUTRO", cfg),
          "PROMO=", g._step_model("PROMOTION", cfg), "DESC=", g._step_model("DESCRIPTION", cfg))
    t0 = time.time()

    # 1) titles（保存済みなら再利用）
    tj = jd / "titles.json"
    if tj.exists():
        cands = json.loads(tj.read_text(encoding="utf-8")); print(f"[titles] 再利用 {len(cands)}件")
    else:
        cands = g.start_titles_job(cfg, jd)
        tj.write_text(json.dumps(cands, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[titles] 生成 {len(cands)}件")

    # 2) structure（保存済みなら再利用）
    sj = jd / "structure.json"
    if sj.exists():
        structure = json.loads(sj.read_text(encoding="utf-8")); print(f"[structure] 再利用 章数{len(structure.get('chapters',[]))}")
    else:
        structure = g.generate_structure_for_review(cfg, jd, cands, 0); print(f"[structure] 生成 章数{len(structure.get('chapters',[]))}")

    plan = g.build_write_plan(structure)
    title = structure.get("title", "")
    char_report = []
    for step in plan:
        kind = step["kind"]
        if kind == "section":
            p = jd / "manuscript" / f"{step['id']}.md"
            g.write_one_section(cfg, jd, structure, title, step)  # 既存はスキップ(冪等)
            n = g.content_char_count(p.read_text(encoding="utf-8")) if p.exists() else 0
            if step["num"] not in (0, 99):
                char_report.append((step["label"], n, 3500 <= n <= 4500))
            print(f"  {step['label']}: {n}字")
        elif kind == "promotion":
            fp = jd / "manuscript" / "98_promotion.md"
            if not (fp.exists() and fp.read_text(encoding='utf-8').strip()):
                fp.write_text(g.clean_public_manuscript(g.generate_promotion(cfg, structure)), encoding="utf-8")
            print("  巻末宣伝 OK")
        elif kind == "description":
            fp = jd / "book_description.md"
            if not (fp.exists() and fp.read_text(encoding='utf-8').strip()):
                fp.write_text(g.clean_public_manuscript(g.generate_description(cfg, structure)), encoding="utf-8")
            print("  紹介文 OK")
        elif kind == "finalize":
            g.finalize_book(cfg, jd, structure, cands, 0); print("  finalize OK")

    import zipfile
    md = jd / "book_full.md"; docx = jd / "book_full.docx"; desc = jd / "book_description.md"
    print("\n=== 成果物 ===")
    for label, p in [("titles.json", tj), ("structure.json", sj), ("book_description.md", desc), ("book_full.md", md), ("book_full.docx", docx)]:
        print(f"  {label}: {'OK' if p.exists() and p.stat().st_size>0 else 'NG'} ({p.stat().st_size if p.exists() else 0}B)")
    print("  docx zip妥当:", docx.exists() and zipfile.is_zipfile(docx))
    print("=== 章別字数(3500-4500) ===")
    allok = True
    for label, n, ok in char_report:
        allok = allok and ok
        print(f"  {label}: {n}字 -> {'合格' if ok else '不合格'}")
    print("  全章合格:", allok)
    print(f"  所要 {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
