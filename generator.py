"""書籍生成コア（v2：2段階UX・H1=4〜5、H2=2〜3、H3 任意）。"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import google.generativeai as genai

import _resource

BASE = _resource.resource_root()
PROMPTS = _resource.resource("prompts")
JOBS = _resource.jobs_dir()


@dataclass
class BookConfig:
    theme: str
    target_layer: str
    author: str
    api_key: str
    model: str = "gemini-2.0-flash"
    references: list = field(default_factory=list)


def _load_prompt(name: str, **kwargs) -> str:
    text = (PROMPTS / name).read_text(encoding="utf-8")
    return text.format(**kwargs)


def _call_gemini(api_key: str, model: str, prompt: str, max_retries: int = 3) -> str:
    genai.configure(api_key=api_key)
    m = genai.GenerativeModel(model)
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            response = m.generate_content(prompt)
            text = (response.text or "").strip()
            if text:
                return text
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Gemini call failed after {max_retries} attempts: {last_err}")


def _references_block(cfg: BookConfig) -> str:
    if not cfg.references:
        return ""
    try:
        from references import render_references_block
        return render_references_block(cfg.references)
    except Exception:
        return ""


def _strip_codefence(s: str) -> str:
    s = re.sub(r"^```(?:json|markdown|md)?\s*\n?", "", s)
    s = re.sub(r"\n?```\s*$", "", s)
    return s.strip()


# ---------------------------------------------------------------------------
# Step 1: タイトル10選を生成
# ---------------------------------------------------------------------------


def generate_titles(cfg: BookConfig) -> list[dict]:
    prompt = _load_prompt(
        "titles.txt",
        theme=cfg.theme,
        target_layer=cfg.target_layer,
        author=cfg.author,
    )
    refs = _references_block(cfg)
    if refs:
        prompt = refs + "\n\n" + prompt
    raw = _strip_codefence(_call_gemini(cfg.api_key, cfg.model, prompt))
    data = json.loads(raw)
    cands = data.get("candidates", [])
    if not isinstance(cands, list) or len(cands) == 0:
        raise RuntimeError("Title generation returned empty candidates")
    for i, c in enumerate(cands, 1):
        c["rank"] = c.get("rank", i)
    return cands[:10]


def render_title_candidates_md(cands: list[dict], adopted_index: int = 0) -> str:
    lines = ["# タイトル10選候補\n"]
    for i, c in enumerate(cands):
        mark = " ★採用" if i == adopted_index else ""
        lines.append(f"## {i+1}位{mark}")
        lines.append(f"- 主タイトル：{c.get('title','')}")
        lines.append(f"- サブタイトル：{c.get('subtitle','')}")
        lines.append(f"- フック型：{c.get('hook_type','')}")
        lines.append(f"- 採用理由：{c.get('reason','')}")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Step 2: 構造（H1=4〜5、H2=2〜3、H3 章合計0〜2）を生成＋検証
# ---------------------------------------------------------------------------


VOICE_TYPES = {
    "公開躊躇型", "具体エピソード型", "数字インパクト型", "45歳の壁型",
    "組織依存脱却型", "正直宣言型", "テンプレ提示型", "時間単価型",
    "FIRE型", "業界権威型",
}
FAILURE_BANK_PREFIXES = {"A", "B", "C", "D", "E", "F", "G"}


def _validate_structure(structure: dict) -> tuple[bool, str]:
    chapters = structure.get("chapters", [])
    if not 4 <= len(chapters) <= 5:
        return False, f"chapters の数が 4〜5 ではない（実際: {len(chapters)}）"
    failure_used: set[str] = set()
    for i, ch in enumerate(chapters):
        sections = ch.get("sections", [])
        if not 2 <= len(sections) <= 3:
            return False, f"第{i+1}章の sections が 2〜3 ではない（実際: {len(sections)}）"
        h3_total = sum(len(s.get("subsections", [])) for s in sections)
        if not 0 <= h3_total <= 2:
            return False, f"第{i+1}章の H3 合計が 0〜2 ではない（実際: {h3_total}）"
        vt = ch.get("voice_type", "")
        if vt and vt not in VOICE_TYPES:
            return False, f"第{i+1}章の voice_type が10型以外（実際: {vt}）"
        fb = ch.get("failure_bank", "")
        prefix = (fb[:1] if fb else "")
        if prefix in FAILURE_BANK_PREFIXES:
            if prefix in failure_used:
                return False, f"failure_bank が章間で重複（{prefix}）"
            failure_used.add(prefix)
    return True, "OK"


def generate_structure(cfg: BookConfig, adopted_title: str, adopted_subtitle: str) -> dict:
    prompt = _load_prompt(
        "structure.txt",
        adopted_title=adopted_title,
        adopted_subtitle=adopted_subtitle,
        theme=cfg.theme,
        target_layer=cfg.target_layer,
        author=cfg.author,
    )
    refs = _references_block(cfg)
    if refs:
        prompt = refs + "\n\n" + prompt
    last_err = ""
    for attempt in range(3):
        raw = _strip_codefence(_call_gemini(cfg.api_key, cfg.model, prompt))
        try:
            structure = json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            last_err = f"JSON parse failed: {exc}"
            continue
        ok, msg = _validate_structure(structure)
        if ok:
            return structure
        last_err = msg
        prompt = (
            prompt
            + f"\n\n【前回の出力でルール違反: {msg}】"
            + "\n指摘事項を解消した正しい JSON だけを返してください。"
        )
    raise RuntimeError(f"Structure validation failed: {last_err}")


# ---------------------------------------------------------------------------
# Step 3: 各章の本文・章末コピペブロック・宣伝・Kindle紹介文
# ---------------------------------------------------------------------------


def _system_prompt(cfg: BookConfig, title: str) -> str:
    return _load_prompt(
        "system.txt",
        author=cfg.author,
        theme=cfg.theme,
        target_layer=cfg.target_layer,
        title=title,
    )


def _format_sections_for_prompt(sections: list[dict]) -> str:
    lines = []
    for s in sections:
        lines.append(f"- H2「{s.get('h2','')}」")
        lines.append(f"  要旨：{s.get('summary','')}")
        for sub in s.get("subsections", []):
            lines.append(f"  - H3「{sub.get('h3','')}」")
    return "\n".join(lines)


def generate_chapter(
    cfg: BookConfig, ch: dict, chapter_number: int, title: str
) -> str:
    system_prompt = _system_prompt(cfg, title)
    sections_text = _format_sections_for_prompt(ch.get("sections", []))
    chapter_title = ch.get("title", "")
    if "：" in chapter_title:
        chapter_title = chapter_title.split("：", 1)[-1]

    user_prompt = f"""
第{chapter_number}章「{chapter_title}」を執筆してください。

【この章の核メッセージ】
{ch.get('key_message','')}

【冒頭1行の型】
{ch.get('voice_type','正直宣言型')}

【挿入する失敗談】
{ch.get('failure_bank','')}

【守るべき節構造（H2/H3 を以下に厳密に従って書く）】
{sections_text}

【書く構造】
1. 冒頭1行（指定の型から派生・1〜2文）
2. 章導入（150〜300字）：失敗談を絡めて読者の痛みを共感
3. 上記の H2 を 2〜3 個（指定どおり）に展開（H3 があれば内部に配置）
4. 章末「この章のまとめ」（3項目の箇条書き）
5. 章末「いますぐの1分アクション」（チェックボックスで1項目）

【出力フォーマット】
- Markdown 形式
- H1 は「# 第{chapter_number}章──{chapter_title}」
- H2 は指定された節タイトルそのまま使用
- H3 がある場合は指定の小節タイトルそのまま使用
- 章末「この章のまとめ」「いますぐの1分」は H2 にカウントしない（独立扱い）
- 出力は Markdown のみ。コードフェンスでラップしない
- マークダウン強調記号「**xxx**」絶対使用禁止
- 命令形「〜しろ／〜してくれ」絶対禁止
- 中流階級KW（年収・時間単価・組織・年商・キャリア・45歳の壁）を最低1回
- 通常段落は「。」で必ず改行（各文を独立段落に）
"""
    refs = _references_block(cfg)
    if refs:
        user_prompt = refs + "\n\n" + user_prompt

    full_prompt = system_prompt + "\n\n---\n\n" + user_prompt
    body = _strip_codefence(_call_gemini(cfg.api_key, cfg.model, full_prompt))
    return body


def generate_reference(cfg: BookConfig, ch: dict, chapter_number: int) -> str:
    prompt = _load_prompt(
        "reference.txt",
        chapter_number=chapter_number,
        chapter_title=ch.get("title", ""),
        key_message=ch.get("key_message", ""),
    )
    return _strip_codefence(_call_gemini(cfg.api_key, cfg.model, prompt))


def generate_promotion(cfg: BookConfig, structure: dict) -> str:
    prompt = _load_prompt(
        "promotion.txt",
        title=structure.get("title", ""),
        author=cfg.author,
        theme=cfg.theme,
        target_layer=cfg.target_layer,
    )
    refs = _references_block(cfg)
    if refs:
        prompt = refs + "\n\n" + prompt
    return _strip_codefence(_call_gemini(cfg.api_key, cfg.model, prompt))


def _structure_summary(structure: dict) -> str:
    chapters = structure.get("chapters", [])
    lines = []
    for i, ch in enumerate(chapters, 1):
        lines.append(f"第{i}章: {ch.get('title','')} → {ch.get('key_message','')}")
    return "\n".join(lines)


def generate_description(cfg: BookConfig, structure: dict) -> str:
    prompt = _load_prompt(
        "description.txt",
        title=structure.get("title", ""),
        subtitle=structure.get("subtitle", ""),
        theme=cfg.theme,
        target_layer=cfg.target_layer,
        author=cfg.author,
        structure_summary=_structure_summary(structure),
    )
    return _strip_codefence(_call_gemini(cfg.api_key, cfg.model, prompt))


# ---------------------------------------------------------------------------
# 2段階の公開関数：start_titles_job / continue_book_job
# ---------------------------------------------------------------------------


def start_titles_job(cfg: BookConfig, job_dir: Path) -> list[dict]:
    job_dir.mkdir(parents=True, exist_ok=True)
    cands = generate_titles(cfg)
    (job_dir / "title_candidates.json").write_text(
        json.dumps(cands, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return cands


def continue_book_job(
    cfg: BookConfig,
    job_dir: Path,
    candidates: list[dict],
    adopted_index: int,
    progress_cb: Callable[[str, int], None],
) -> dict:
    if not 0 <= adopted_index < len(candidates):
        raise ValueError(f"adopted_index out of range: {adopted_index}")

    adopted = candidates[adopted_index]
    title = adopted.get("title", "")
    subtitle = adopted.get("subtitle", "")

    title_md = render_title_candidates_md(candidates, adopted_index)
    (job_dir / "title_candidates.md").write_text(title_md, encoding="utf-8")

    progress_cb("構造（H1/H2/H3）を構築中...", 8)
    structure = generate_structure(cfg, title, subtitle)
    (job_dir / "structure.json").write_text(
        json.dumps(structure, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    manuscript_dir = job_dir / "manuscript"
    manuscript_dir.mkdir(parents=True, exist_ok=True)

    chapters = structure.get("chapters", [])
    intro = structure.get("intro", {})
    outro = structure.get("outro", {})

    sections = [intro] + list(chapters) + [outro]
    total_sections = len(sections)
    base_pct = 15
    end_pct = 80
    span = end_pct - base_pct

    for i, ch in enumerate(sections):
        is_intro = ch.get("id", "").startswith("00")
        is_outro = ch.get("id", "").startswith("99")
        ch_num_label = (
            "はじめに" if is_intro else "おわりに" if is_outro else f"第{i}章"
        )
        progress_pct = base_pct + int(span * (i + 0.4) / total_sections)
        progress_cb(
            f"{ch_num_label}「{ch.get('title','')}」を執筆中...", progress_pct
        )

        if not ch.get("sections"):
            ch["sections"] = [
                {"h2": "（節）", "summary": ch.get("key_message", ""), "subsections": []}
            ]
        chapter_number = 0 if is_intro else (99 if is_outro else i)
        body = generate_chapter(cfg, ch, chapter_number, title)

        full = body.rstrip()
        if not is_intro and not is_outro:
            progress_pct = base_pct + int(span * (i + 0.7) / total_sections)
            progress_cb(
                f"{ch_num_label}のコピペブロックを生成中...", progress_pct
            )
            ref_block = generate_reference(cfg, ch, chapter_number)
            full = full + "\n\n" + ref_block + "\n"

        out_path = manuscript_dir / f"{ch.get('id','section')}.md"
        out_path.write_text(full, encoding="utf-8")

    progress_cb("巻末の宣伝セクションを作成中...", 84)
    promo = generate_promotion(cfg, structure)
    (manuscript_dir / "98_promotion.md").write_text(promo, encoding="utf-8")

    progress_cb("Kindle 紹介文を生成中...", 88)
    desc = generate_description(cfg, structure)
    (job_dir / "book_description.md").write_text(desc, encoding="utf-8")

    progress_cb("統合 Markdown を生成中...", 92)
    merged_md = build_merged_md(title, subtitle, cfg.author, manuscript_dir, structure)
    merged_md_path = job_dir / "book_full.md"
    merged_md_path.write_text(merged_md, encoding="utf-8")

    progress_cb("Word に変換中...", 96)
    docx_path = job_dir / "book_full.docx"
    convert_to_docx(merged_md_path, docx_path)

    progress_cb("完了しました。", 100)
    return {
        "title": title,
        "subtitle": subtitle,
        "md_path": str(merged_md_path),
        "docx_path": str(docx_path),
        "chapter_count": len(chapters),
        "char_count": len(merged_md),
        "adopted_index": adopted_index,
    }


# ---------------------------------------------------------------------------
# 段落・改ページ・統合
# ---------------------------------------------------------------------------


PAGEBREAK_RAW = (
    "```{=openxml}\n"
    '<w:p><w:r><w:br w:type="page"/></w:r></w:p>\n'
    "```"
)
HEADING_RE = re.compile(r"^(#{1,3})\s")
FENCE_RE = re.compile(r"^\s*```")


def insert_pagebreaks_before_headings(body: str) -> str:
    lines = body.split("\n")
    out: list[str] = []
    in_code = False
    for line in lines:
        if FENCE_RE.match(line):
            in_code = not in_code
            out.append(line)
            continue
        if not in_code and HEADING_RE.match(line):
            while out and out[-1] == "":
                out.pop()
            if out:
                out.append("")
            out.append(PAGEBREAK_RAW)
            out.append("")
            out.append(line)
            continue
        out.append(line)
    return "\n".join(out)


def split_by_period(paragraph: str) -> list[str]:
    paragraph = paragraph.strip()
    if not paragraph:
        return []
    parts = re.split(r"(。)", paragraph)
    sentences = []
    buf = ""
    for p in parts:
        buf += p
        if p == "。":
            sentences.append(buf.strip())
            buf = ""
    if buf.strip():
        sentences.append(buf.strip())
    return sentences


def apply_period_breaks(text: str) -> str:
    out: list[str] = []
    in_code = False
    paragraph_buffer: list[str] = []

    def flush():
        if not paragraph_buffer:
            return
        joined = " ".join(s for s in paragraph_buffer if s)
        joined = re.sub(r"\s+", " ", joined).strip()
        paragraph_buffer.clear()
        if not joined:
            return
        sentences = split_by_period(joined)
        for i, s in enumerate(sentences):
            out.append(s)
            if i < len(sentences) - 1:
                out.append("")

    for line in text.split("\n"):
        stripped = line.strip()
        if FENCE_RE.match(line):
            flush()
            out.append(line)
            in_code = not in_code
            continue
        if in_code:
            out.append(line)
            continue
        if not stripped:
            flush()
            if not out or out[-1] != "":
                out.append("")
            continue
        if stripped.startswith("#"):
            flush()
            if out and out[-1] != "":
                out.append("")
            out.append(line)
            out.append("")
            continue
        if stripped.startswith("|"):
            flush()
            out.append(line)
            continue
        if re.match(r"^([-*]|\d+\.|\[[ x]\])\s", stripped):
            flush()
            out.append(line)
            continue
        if stripped.startswith(">"):
            flush()
            out.append(line)
            continue
        if re.match(r"^─{3,}$", stripped) or stripped == "---":
            flush()
            out.append(line)
            continue
        paragraph_buffer.append(stripped)

    flush()
    cleaned: list[str] = []
    prev_empty = False
    for ln in out:
        if ln == "":
            if prev_empty:
                continue
            prev_empty = True
        else:
            prev_empty = False
        cleaned.append(ln)
    result = "\n".join(cleaned)
    if not result.endswith("\n"):
        result += "\n"
    return result


def build_merged_md(
    title: str, subtitle: str, author: str, manuscript_dir: Path, structure: dict
) -> str:
    cover = (
        f"% {title}\n"
        f"% {author}\n\n"
        f"# {title}\n\n"
        f"## {subtitle}\n\n"
        f"著者：{author}\n\n"
    )

    intro = structure.get("intro", {})
    outro = structure.get("outro", {})
    chapters = structure.get("chapters", [])

    order_ids: list[str] = []
    if intro.get("id"):
        order_ids.append(intro["id"])
    for ch in chapters:
        if ch.get("id"):
            order_ids.append(ch["id"])
    if outro.get("id"):
        order_ids.append(outro["id"])
    order_ids.append("98_promotion")

    body_parts: list[str] = []
    for fid in order_ids:
        fpath = manuscript_dir / f"{fid}.md"
        if not fpath.exists():
            continue
        text = fpath.read_text(encoding="utf-8")
        text = apply_period_breaks(text)
        body_parts.append(text.strip())

    body = "\n\n".join(body_parts)
    body_with_breaks = insert_pagebreaks_before_headings(body)
    return cover + body_with_breaks + "\n"


def convert_to_docx(md_path: Path, docx_path: Path) -> None:
    import pypandoc

    extra_args = ["--standalone", "--toc", "--toc-depth=3"]
    ref_doc = _resource.resource("templates", "reference_v7.docx")
    if ref_doc.exists():
        extra_args.append(f"--reference-doc={ref_doc}")

    pypandoc.convert_file(
        str(md_path),
        to="docx",
        outputfile=str(docx_path),
        format="markdown+raw_attribute",
        extra_args=extra_args,
    )
