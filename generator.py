"""書籍生成コア。Gemini API で目次→章本文→3層コピペを生成する。"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import google.generativeai as genai

BASE = Path(__file__).resolve().parent
PROMPTS = BASE / "prompts"
JOBS = BASE / "jobs"


@dataclass
class BookConfig:
    theme: str
    target_layer: str
    author: str
    api_key: str
    model: str = "gemini-2.0-flash-exp"


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
            text = response.text.strip()
            if text:
                return text
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Gemini call failed after {max_retries} attempts: {last_err}")


def generate_outline(cfg: BookConfig) -> dict:
    prompt = _load_prompt(
        "outline.txt",
        theme=cfg.theme,
        target_layer=cfg.target_layer,
        author=cfg.author,
    )
    raw = _call_gemini(cfg.api_key, cfg.model, prompt)
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


def generate_chapter(cfg: BookConfig, chapter: dict, chapter_number: int, title: str) -> str:
    system_prompt = _load_prompt(
        "system.txt",
        author=cfg.author,
        theme=cfg.theme,
        target_layer=cfg.target_layer,
        title=title,
    )
    prompt = _load_prompt(
        "chapter.txt",
        system_prompt=system_prompt,
        chapter_number=chapter_number,
        chapter_title=chapter["title"].split("：", 1)[-1] if "：" in chapter["title"] else chapter["title"],
        key_message=chapter.get("key_message", ""),
        voice_type=chapter.get("voice_type", "正直宣言型"),
        failure_bank=chapter.get("failure_bank", ""),
    )
    body = _call_gemini(cfg.api_key, cfg.model, prompt)
    body = re.sub(r"^```(?:markdown|md)?\s*\n", "", body)
    body = re.sub(r"\n```\s*$", "", body)
    return body.strip()


def generate_reference(cfg: BookConfig, chapter: dict, chapter_number: int) -> str:
    prompt = _load_prompt(
        "reference.txt",
        chapter_number=chapter_number,
        chapter_title=chapter["title"],
        key_message=chapter.get("key_message", ""),
    )
    block = _call_gemini(cfg.api_key, cfg.model, prompt)
    block = re.sub(r"^```(?:markdown|md)?\s*\n", "", block)
    block = re.sub(r"\n```\s*$", "", block)
    return block.strip()


def generate_book(
    cfg: BookConfig,
    job_dir: Path,
    progress_cb: Callable[[str, int], None],
) -> dict:
    job_dir.mkdir(parents=True, exist_ok=True)
    manuscript_dir = job_dir / "manuscript"
    manuscript_dir.mkdir(exist_ok=True)

    progress_cb("目次を作成中...", 5)
    outline = generate_outline(cfg)
    (job_dir / "outline.json").write_text(
        json.dumps(outline, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    title = outline["title"]
    subtitle = outline.get("subtitle", "")
    chapters = outline["chapters"]
    total = len(chapters)

    for i, ch in enumerate(chapters):
        chapter_number = i if ch["id"].startswith(("00", "99")) else int(ch["id"].split("_")[1])
        progress_pct = 5 + int(85 * (i + 0.3) / total)
        progress_cb(f"第{i+1}/{total}章「{ch['title']}」の本文を生成中...", progress_pct)
        body = generate_chapter(cfg, ch, chapter_number, title)

        progress_pct = 5 + int(85 * (i + 0.7) / total)
        progress_cb(f"第{i+1}/{total}章のコピペブロックを生成中...", progress_pct)
        if ch["id"].startswith("99"):
            reference = ""
        else:
            reference = generate_reference(cfg, ch, chapter_number)

        full = body
        if reference:
            full = full.rstrip() + "\n\n" + reference + "\n"

        out_path = manuscript_dir / f"{ch['id']}.md"
        out_path.write_text(full, encoding="utf-8")

    progress_cb("統合 Markdown を生成中...", 92)
    merged_md = build_merged_md(title, subtitle, cfg.author, manuscript_dir, chapters)
    merged_md_path = job_dir / "book_full.md"
    merged_md_path.write_text(merged_md, encoding="utf-8")

    progress_cb("Word ファイルに変換中...", 96)
    docx_path = job_dir / "book_full.docx"
    convert_to_docx(merged_md_path, docx_path)

    progress_cb("完了しました。", 100)
    return {
        "title": title,
        "subtitle": subtitle,
        "md_path": str(merged_md_path),
        "docx_path": str(docx_path),
        "chapter_count": total,
        "char_count": len(merged_md),
    }


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
    title: str, subtitle: str, author: str, manuscript_dir: Path, chapters: list[dict]
) -> str:
    cover = (
        f"% {title}\n"
        f"% {author}\n\n"
        f"# {title}\n\n"
        f"## {subtitle}\n\n"
        f"著者：{author}\n\n"
    )

    body_parts: list[str] = []
    for ch in chapters:
        fpath = manuscript_dir / f"{ch['id']}.md"
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

    pypandoc.convert_file(
        str(md_path),
        to="docx",
        outputfile=str(docx_path),
        format="markdown+raw_attribute",
        extra_args=["--standalone", "--toc", "--toc-depth=3"],
    )
