"""書籍生成コア（v2：2段階UX・H1=4〜5、H2=2〜3、H3 任意）。"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import time
import zipfile
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from xml.etree import ElementTree as ET

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
    # v2.0: 著者プロファイル（フォームで都度入力・複数プロファイルを localStorage に保存）
    profile_name: str = ""
    profile_author_bio: str = ""
    profile_tone: str = ""
    profile_target_keywords: list[str] = field(default_factory=list)
    profile_failure_bank: list[str] = field(default_factory=list)
    profile_voice_types: list[str] = field(default_factory=list)


def _profile_kwargs(cfg: BookConfig) -> dict:
    """プロファイル系の format() 引数を一括生成。プロンプト共通変数。"""
    kw_str = ", ".join(k for k in (cfg.profile_target_keywords or []) if k) or "（プロファイル未設定）"
    fb_block = (
        "\n".join(f"- {fb}" for fb in cfg.profile_failure_bank if fb)
        or "（失敗談バンク未設定。失敗談の引用は省略可）"
    )
    vt_block = (
        ", ".join(vt for vt in cfg.profile_voice_types if vt)
        or "（voice_type 未設定。型に縛られず素直な文体で書いて構わない）"
    )
    return {
        "profile_name": cfg.profile_name or "（無名）",
        "profile_author_bio": cfg.profile_author_bio or "（著者経歴の指定なし）",
        "profile_tone": cfg.profile_tone or "丁寧調を基調とし、命令形は使わない。マークダウン強調記号（**xxx**）は使わない。",
        "profile_target_keywords": kw_str,
        "profile_failure_bank_block": fb_block,
        "profile_voice_types_block": vt_block,
    }


def _clean_profile_kwargs(cfg: BookConfig) -> dict:
    """Prompt variables for optional per-author profile fields."""
    keywords = ", ".join(k for k in (cfg.profile_target_keywords or []) if k) or "指定なし"
    failure_bank = "\n".join(f"- {fb}" for fb in cfg.profile_failure_bank if fb) or "指定なし"
    voice_types = "\n".join(f"- {vt}" for vt in cfg.profile_voice_types if vt) or "指定なし"
    return {
        "profile_name": cfg.profile_name or cfg.author or "指定なし",
        "profile_author_bio": cfg.profile_author_bio or "指定なし",
        "profile_tone": cfg.profile_tone or "丁寧で読みやすい実務調。過度な煽り、命令口調、装飾的な強調は使わない。",
        "profile_target_keywords": keywords,
        "profile_failure_bank_block": failure_bank,
        "profile_voice_types_block": voice_types,
    }


def _load_prompt(name: str, **kwargs) -> str:
    """プロンプトテンプレを読み込んで format。

    `cfg=BookConfig` を渡すと、profile_* の format 変数が自動注入される。
    呼び出し側で同名 kwarg を指定した場合はそちらを優先（上書き）。
    """
    text = (PROMPTS / name).read_text(encoding="utf-8")
    cfg = kwargs.pop("cfg", None)
    if cfg is not None:
        for k, v in _clean_profile_kwargs(cfg).items():
            kwargs.setdefault(k, v)
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
        cfg=cfg,
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


def _validate_structure(structure: dict, cfg: BookConfig | None = None) -> tuple[bool, str]:
    """構造ルールを検証する。voice_type / failure_bank の許容セットはプロファイル依存。

    プロファイルに voice_types / failure_bank が未設定なら、その項目の検証はスキップする
    （マルチユーザー対応：他者プロファイルで型未指定でも生成できる）。
    """
    chapters = structure.get("chapters", [])
    if not 4 <= len(chapters) <= 5:
        return False, f"chapters の数が 4〜5 ではない（実際: {len(chapters)}）"

    allowed_voice_types: set[str] = set()
    failure_bank_prefixes: set[str] = set()
    if False and cfg is not None:
        allowed_voice_types = {vt for vt in cfg.profile_voice_types if vt}
        for fb in cfg.profile_failure_bank:
            prefix = (fb.strip()[:1] if fb else "")
            if prefix and prefix.isalpha():
                failure_bank_prefixes.add(prefix.upper())

    failure_used: set[str] = set()
    for i, ch in enumerate(chapters):
        sections = ch.get("sections", [])
        if not 2 <= len(sections) <= 3:
            return False, f"第{i+1}章の sections が 2〜3 ではない（実際: {len(sections)}）"
        h3_total = sum(len(s.get("subsections", [])) for s in sections)
        if not 0 <= h3_total <= 2:
            return False, f"第{i+1}章の H3 合計が 0〜2 ではない（実際: {h3_total}）"

        if allowed_voice_types:
            vt = ch.get("voice_type", "")
            if vt and vt not in allowed_voice_types:
                return False, f"第{i+1}章の voice_type がプロファイル定義外（実際: {vt}）"

        if failure_bank_prefixes:
            fb = ch.get("failure_bank", "")
            prefix = (fb[:1].upper() if fb else "")
            if prefix and prefix in failure_bank_prefixes:
                if prefix in failure_used:
                    return False, f"failure_bank が章間で重複（{prefix}）"
                failure_used.add(prefix)
    return True, "OK"


def generate_structure(cfg: BookConfig, adopted_title: str, adopted_subtitle: str) -> dict:
    prompt = _load_prompt(
        "structure.txt",
        cfg=cfg,
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
        ok, msg = _validate_structure(structure, cfg)
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
        cfg=cfg,
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
    cfg: BookConfig, ch: dict, chapter_number: int, title: str, chapter_label: str | None = None
) -> str:
    system_prompt = _system_prompt(cfg, title)
    sections_text = _format_sections_for_prompt(ch.get("sections", []))
    effective_label = chapter_label or f"第{chapter_number}章"
    chapter_title = ch.get("title", "")
    if "：" in chapter_title:
        chapter_title = chapter_title.split("：", 1)[-1]

    normalized_title = re.sub(r"^\s*#*\s*", "", chapter_title).strip()
    normalized_title = re.sub(r"^\s*第\d+章\s*", "", normalized_title).strip()
    if normalized_title in {effective_label, "\u306f\u3058\u3081\u306b", "\u304a\u308f\u308a\u306b"}:
        chapter_title = ""

    user_prompt = _load_prompt(
        "chapter.txt",
        cfg=cfg,
        chapter_number=chapter_number,
        chapter_label=effective_label,
        chapter_title=chapter_title,
        key_message=ch.get("key_message", ""),
        voice_type=ch.get("voice_type", ""),
        failure_bank=ch.get("failure_bank", ""),
        sections_text=sections_text,
    )

    refs = _references_block(cfg)
    if refs:
        user_prompt = refs + "\n\n" + user_prompt

    full_prompt = system_prompt + "\n\n---\n\n" + user_prompt
    body = _strip_codefence(_call_gemini(cfg.api_key, cfg.model, full_prompt))
    return body


def generate_reference(cfg: BookConfig, ch: dict, chapter_number: int, chapter_label: str | None = None) -> str:
    prompt = _load_prompt(
        "reference.txt",
        cfg=cfg,
        chapter_number=chapter_number,
        chapter_label=chapter_label or f"第{chapter_number}章",
        chapter_title=ch.get("title", ""),
        key_message=ch.get("key_message", ""),
    )
    return _strip_codefence(_call_gemini(cfg.api_key, cfg.model, prompt))


def generate_promotion(cfg: BookConfig, structure: dict) -> str:
    prompt = _load_prompt(
        "promotion.txt",
        cfg=cfg,
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
        cfg=cfg,
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


def regenerate_titles_bestseller(cfg: BookConfig, prev_candidates: list[dict]) -> list[dict]:
    """ベストセラー強化版タイトル10選を再生成。前回案を渡して差別化を強制する。"""
    prompt = _load_prompt(
        "titles_bestseller.txt",
        cfg=cfg,
        theme=cfg.theme,
        target_layer=cfg.target_layer,
        author=cfg.author,
        previous_candidates_json=json.dumps(prev_candidates, ensure_ascii=False, indent=2),
    )
    refs = _references_block(cfg)
    if refs:
        prompt = refs + "\n\n" + prompt
    raw = _strip_codefence(_call_gemini(cfg.api_key, cfg.model, prompt))
    data = json.loads(raw)
    cands = data.get("candidates", [])
    if not isinstance(cands, list) or len(cands) == 0:
        raise RuntimeError("Title regeneration returned empty candidates")
    for i, c in enumerate(cands, 1):
        c["rank"] = c.get("rank", i)
    return cands[:10]


def generate_structure_bestseller(
    cfg: BookConfig,
    adopted_title: str,
    adopted_subtitle: str,
    prev_structure: dict,
) -> dict:
    """ベストセラー強化版章立てを再生成。前回構造を渡して差別化を強制する。"""
    base_prompt = _load_prompt(
        "structure_bestseller.txt",
        cfg=cfg,
        adopted_title=adopted_title,
        adopted_subtitle=adopted_subtitle,
        theme=cfg.theme,
        target_layer=cfg.target_layer,
        author=cfg.author,
        previous_structure_json=json.dumps(prev_structure, ensure_ascii=False, indent=2),
    )
    refs = _references_block(cfg)
    if refs:
        base_prompt = refs + "\n\n" + base_prompt
    last_err = ""
    prompt = base_prompt
    for _ in range(3):
        raw = _strip_codefence(_call_gemini(cfg.api_key, cfg.model, prompt))
        try:
            structure = json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            last_err = f"JSON parse failed: {exc}"
            continue
        ok, msg = _validate_structure(structure, cfg)
        if ok:
            return structure
        last_err = msg
        prompt = (
            base_prompt
            + f"\n\n【前回の出力でルール違反: {msg}】"
            + "\n指摘事項を解消した正しい JSON だけを返してください。"
        )
    raise RuntimeError(f"Bestseller structure validation failed: {last_err}")



def generate_structure_for_review(
    cfg: BookConfig,
    job_dir: Path,
    candidates: list[dict],
    adopted_index: int,
) -> dict:
    """採用タイトルから章立てを生成し structure.json に保存。本編は生成しない。"""
    if not 0 <= adopted_index < len(candidates):
        raise ValueError(f"adopted_index out of range: {adopted_index}")
    adopted = candidates[adopted_index]
    title = adopted.get("title", "")
    subtitle = adopted.get("subtitle", "")
    structure = generate_structure(cfg, title, subtitle)
    (job_dir / "structure.json").write_text(
        json.dumps(structure, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return structure


def start_writing(
    cfg: BookConfig,
    job_dir: Path,
    structure: dict,
    candidates: list[dict],
    adopted_index: int,
    progress_cb: Callable[[str, int], None],
) -> dict:
    """ユーザー承認済み章立てから本編を書き出す。structure は外部から受け取る。"""
    if not 0 <= adopted_index < len(candidates):
        raise ValueError(f"adopted_index out of range: {adopted_index}")

    adopted = candidates[adopted_index]
    title = adopted.get("title", "")
    subtitle = adopted.get("subtitle", "")

    title_md = render_title_candidates_md(candidates, adopted_index)
    (job_dir / "title_candidates.md").write_text(title_md, encoding="utf-8")

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
        chapter_label = "はじめに" if is_intro else ("おわりに" if is_outro else f"第{i}章")
        body = clean_public_manuscript(generate_chapter(cfg, ch, chapter_number, title, chapter_label))

        full = body.rstrip()
        if not is_intro and not is_outro:
            progress_pct = base_pct + int(span * (i + 0.7) / total_sections)
            progress_cb(
                f"{ch_num_label}のコピペブロックを生成中...", progress_pct
            )
            ref_block = generate_reference(cfg, ch, chapter_number, chapter_label)
            full = clean_public_manuscript(full + "\n\n" + ref_block + "\n")

        out_path = manuscript_dir / f"{ch.get('id','section')}.md"
        out_path.write_text(clean_public_manuscript(full), encoding="utf-8")

    progress_cb("巻末の宣伝セクションを作成中...", 84)
    promo = clean_public_manuscript(generate_promotion(cfg, structure))
    (manuscript_dir / "98_promotion.md").write_text(promo, encoding="utf-8")

    progress_cb("Kindle 紹介文を生成中...", 88)
    desc = clean_public_manuscript(generate_description(cfg, structure))
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


HEADING_RE = re.compile(r"^(#{1,3})\s")
FENCE_RE = re.compile(r"^\s*```")


def clean_public_manuscript(text: str) -> str:
    text = re.sub(r"```{=openxml}.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"<w:p>\s*<w:r>\s*<w:br\s+w:type=['\"]page['\"]\s*/>\s*</w:r>\s*</w:p>", "", text)
    text = re.sub(r"```{=openxml}\s*```", "", text, flags=re.MULTILINE)
    text = re.sub(r"(?m)^\s*%\s+.*$", "", text)
    text = re.sub(r"「\s*」", "", text)
    text = re.sub(r"(?m)^(\s*#{0,6}\s*)[▶▸►‣›>・●○■□◆◇◦]+\s*", r"\1", text)
    text = re.sub(r"(?m)^(\s*#{0,6}\s*)[\"'“”‘’]+\s*", r"\1", text)
    text = re.sub(r"([。\n])\s*[▶▸►‣›>・●○■□◆◇◦]+\s*", r"\1", text)
    text = re.sub(r"(?m)^#\s*.*99.*$", "# おわりに", text)
    text = re.sub(r"(?m)^.*第99章.*$", "おわりに", text)
    text = re.sub(r"(?m)^#\s*第99章\s*", "# おわりに ", text)
    text = re.sub(r"(?m)^第99章\s*", "おわりに ", text)
    text = re.sub(r"(?m)^(\s*)[*]\s+", r"\1", text)
    text = re.sub(r"(?m)^(\s*)[-]\s+", r"\1", text)
    text = text.replace("*", "")
    text = re.sub(r"(?m)^(#+\s*)?(\u306f\u3058\u3081\u306b)(?:\s+\2)+\s*$", r"\1\2", text)
    text = re.sub(r"(?m)^(#+\s*)?(\u304a\u308f\u308a\u306b)(?:\s+\2)+\s*$", r"\1\2", text)
    text = re.sub(r"(\u306f\u3058\u3081\u306b)\s+\1", r"\1", text)
    text = re.sub(r"(\u304a\u308f\u308a\u306b)\s+\1", r"\1", text)
    text = re.sub(r"(?im)^.*(ChatGPT|Gemini|AI\s*generated).*$", "", text)
    text = re.sub(r"(?i)AI生成", "", text)
    text = re.sub(r"(?i)AIが作成", "", text)
    text = re.sub(r"(?i)AIによる", "", text)
    text = re.sub(r"(?i)ChatGPT", "", text)
    text = re.sub(r"(?i)Gemini", "", text)
    text = re.sub(r"(?i)AI\s*generated", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


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


def _is_markdown_spacing_heading(line: str) -> bool:
    stripped = line.strip()
    return bool(re.match(r"^#{1,3}\s+\S", stripped))


def ensure_markdown_heading_spacing(text: str) -> str:
    lines = text.split("\n")
    out: list[str] = []
    for idx, line in enumerate(lines):
        out.append(line)
        if _is_markdown_spacing_heading(line):
            next_line = lines[idx + 1] if idx + 1 < len(lines) else ""
            if next_line.strip():
                out.append("")
    result = "\n".join(out)
    if not result.endswith("\n"):
        result += "\n"
    return result


def build_merged_md(
    title: str, subtitle: str, author: str, manuscript_dir: Path, structure: dict
) -> str:
    cover = (
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
    merged = clean_public_manuscript(cover + body + "\n")
    return ensure_markdown_heading_spacing(merged)


def convert_to_docx(md_path: Path, docx_path: Path) -> None:
    import pypandoc

    extra_args = ["--standalone", "--toc", "--toc-depth=3"]
    # v1.2: 視認性向上版（コピペ枠・ケーススタディBOX のスタイル拡張）を優先。
    # v8 が無ければ v7 にフォールバック、それも無ければ Pandoc 既定。
    ref_v8 = _resource.resource("templates", "reference_v8.docx")
    ref_v7 = _resource.resource("templates", "reference_v7.docx")
    if ref_v8.exists():
        extra_args.append(f"--reference-doc={ref_v8}")
    elif ref_v7.exists():
        extra_args.append(f"--reference-doc={ref_v7}")

    pypandoc.convert_file(
        str(md_path),
        to="docx",
        outputfile=str(docx_path),
        format="markdown+raw_attribute",
        extra_args=extra_args,
    )
    move_word_toc_after_intro(docx_path)


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
ET.register_namespace("w", WORD_NS)

HEADING_AFTER_SPACING_STYLES = {"Title", "TOCHeading", "Heading1", "Heading2", "Heading3"}
HEADING_AFTER_SPACING_TWIPS = "80"
WORD_STYLE_MAP = {
    "Title": "BookTitle",
    "TOCHeading": "BookTOCHeading",
    "Heading1": "BookHeading1",
    "Heading2": "BookHeading2",
    "Heading3": "BookHeading3",
}
WORD_TOC_FIELD_INSTRUCTION = 'TOC \\h \\z \\t "BookHeading1,1,BookHeading2,2,BookHeading3,3"'


def _w_tag(name: str) -> str:
    return f"{{{WORD_NS}}}{name}"


def _node_text(node: ET.Element) -> str:
    return "".join(t.text or "" for t in node.iter(_w_tag("t")))


def _paragraph_style(node: ET.Element) -> str:
    p_pr = node.find(_w_tag("pPr"))
    if p_pr is None:
        return ""
    p_style = p_pr.find(_w_tag("pStyle"))
    if p_style is None:
        return ""
    return p_style.attrib.get(_w_tag("val"), "")


def _ensure_heading_after_spacing(paragraph: ET.Element) -> None:
    if paragraph.tag != _w_tag("p"):
        return
    if _paragraph_style(paragraph) not in HEADING_AFTER_SPACING_STYLES:
        return
    p_pr = paragraph.find(_w_tag("pPr"))
    if p_pr is None:
        p_pr = ET.Element(_w_tag("pPr"))
        paragraph.insert(0, p_pr)
    spacing = p_pr.find(_w_tag("spacing"))
    if spacing is None:
        spacing = ET.SubElement(p_pr, _w_tag("spacing"))
    spacing.set(_w_tag("after"), HEADING_AFTER_SPACING_TWIPS)


def apply_heading_after_spacing(body: ET.Element) -> None:
    for paragraph in body.iter(_w_tag("p")):
        _ensure_heading_after_spacing(paragraph)


def _remove_outline_level(style: ET.Element) -> None:
    p_pr = style.find(_w_tag("pPr"))
    if p_pr is None:
        return
    outline = p_pr.find(_w_tag("outlineLvl"))
    if outline is not None:
        p_pr.remove(outline)


def _style_attr(style: ET.Element, tag: str) -> ET.Element | None:
    return style.find(_w_tag(tag))


def _custom_style_name(style_id: str) -> str:
    return {
        "BookTitle": "Book Title",
        "BookTOCHeading": "Book TOC Heading",
        "BookHeading1": "Book Heading 1",
        "BookHeading2": "Book Heading 2",
        "BookHeading3": "Book Heading 3",
    }[style_id]


def _customize_style(source_style: ET.Element, new_style_id: str) -> ET.Element:
    style = deepcopy(source_style)
    style.set(_w_tag("styleId"), new_style_id)

    name = _style_attr(style, "name")
    if name is None:
        name = ET.SubElement(style, _w_tag("name"))
    name.set(_w_tag("val"), _custom_style_name(new_style_id))

    for tag in ("link", "uiPriority", "semiHidden", "unhideWhenUsed", "qFormat", "rsid"):
        elem = _style_attr(style, tag)
        if elem is not None:
            style.remove(elem)

    based_on = _style_attr(style, "basedOn")
    if based_on is not None:
        based_on.set(_w_tag("val"), "DefaultParagraphFont" if new_style_id == "BookTitle" else "Normal")

    p_pr = _style_attr(style, "pPr")
    if p_pr is not None:
        outline = p_pr.find(_w_tag("outlineLvl"))
        if outline is not None:
            p_pr.remove(outline)
    return style


def _install_custom_word_styles(styles_root: ET.Element) -> None:
    originals = {
        style.attrib.get(_w_tag("styleId"), ""): style
        for style in styles_root.findall(_w_tag("style"))
    }
    for source_id, custom_id in WORD_STYLE_MAP.items():
        source_style = originals.get(source_id)
        if source_style is None:
            continue
        styles_root.append(_customize_style(source_style, custom_id))


def _rewrite_paragraph_styles(body: ET.Element) -> None:
    for paragraph in body.iter(_w_tag("p")):
        p_pr = paragraph.find(_w_tag("pPr"))
        if p_pr is None:
            continue
        p_style = p_pr.find(_w_tag("pStyle"))
        if p_style is None:
            continue
        current = p_style.attrib.get(_w_tag("val"), "")
        if current in WORD_STYLE_MAP:
            p_style.set(_w_tag("val"), WORD_STYLE_MAP[current])


def _rewrite_word_toc_instruction(toc_node: ET.Element) -> None:
    for instr in toc_node.iter(_w_tag("instrText")):
        if "TOC" in (instr.text or ""):
            instr.text = WORD_TOC_FIELD_INSTRUCTION
            return


def remove_pagebreak_paragraphs(container: ET.Element) -> None:
    for child in list(container):
        if _is_pagebreak_paragraph(child):
            container.remove(child)
        else:
            remove_pagebreak_paragraphs(child)


def _is_heading1(node: ET.Element) -> bool:
    return node.tag == _w_tag("p") and _paragraph_style(node) == "Heading1"


def _is_pagebreak_paragraph(node: ET.Element) -> bool:
    if node.tag != _w_tag("p"):
        return False
    for br in node.iter(_w_tag("br")):
        if br.attrib.get(_w_tag("type")) == "page":
            return True
    return False


def _is_toc_sdt(node: ET.Element) -> bool:
    if node.tag != _w_tag("sdt"):
        return False
    for instr in node.iter(_w_tag("instrText")):
        if "TOC" in (instr.text or ""):
            return True
    return False


def _make_word_toc_sdt() -> ET.Element:
    sdt = ET.Element(_w_tag("sdt"))
    sdt_pr = ET.SubElement(sdt, _w_tag("sdtPr"))
    doc_part_obj = ET.SubElement(sdt_pr, _w_tag("docPartObj"))
    ET.SubElement(doc_part_obj, _w_tag("docPartGallery"), {_w_tag("val"): "Table of Contents"})
    ET.SubElement(doc_part_obj, _w_tag("docPartUnique"))

    sdt_content = ET.SubElement(sdt, _w_tag("sdtContent"))
    heading_p = ET.SubElement(sdt_content, _w_tag("p"))
    heading_p_pr = ET.SubElement(heading_p, _w_tag("pPr"))
    ET.SubElement(heading_p_pr, _w_tag("pStyle"), {_w_tag("val"): "TOCHeading"})
    ET.SubElement(heading_p_pr, _w_tag("spacing"), {_w_tag("after"): HEADING_AFTER_SPACING_TWIPS})
    heading_r = ET.SubElement(heading_p, _w_tag("r"))
    heading_t = ET.SubElement(heading_r, _w_tag("t"))
    heading_t.text = "Table of Contents"

    field_p = ET.SubElement(sdt_content, _w_tag("p"))
    field_r = ET.SubElement(field_p, _w_tag("r"))
    ET.SubElement(field_r, _w_tag("fldChar"), {_w_tag("fldCharType"): "begin", _w_tag("dirty"): "true"})
    instr = ET.SubElement(field_r, _w_tag("instrText"), {"{http://www.w3.org/XML/1998/namespace}space": "preserve"})
    instr.text = WORD_TOC_FIELD_INSTRUCTION
    ET.SubElement(field_r, _w_tag("fldChar"), {_w_tag("fldCharType"): "separate"})
    ET.SubElement(field_r, _w_tag("fldChar"), {_w_tag("fldCharType"): "end"})
    return sdt


def _is_intro_heading(node: ET.Element) -> bool:
    return "\u306f\u3058\u3081\u306b" in _node_text(node).strip()


def move_word_toc_after_intro(docx_path: Path) -> None:
    """Move Pandoc's Word TOC field after the intro body.

    The TOC remains the Word/Pandoc `w:sdt` field generated by `--toc`.
    This function changes only its position in `word/document.xml`.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(docx_path, "r") as zin:
            zin.extractall(tmp_path)

        document_xml = tmp_path / "word" / "document.xml"
        tree = ET.parse(document_xml)
        root = tree.getroot()
        body = root.find(_w_tag("body"))
        if body is None:
            return

        toc_node: ET.Element | None = None
        for child in list(body):
            if _is_toc_sdt(child):
                toc_node = child
                body.remove(child)
                break
        if toc_node is None:
            toc_node = _make_word_toc_sdt()
        else:
            _rewrite_word_toc_instruction(toc_node)

        children = list(body)
        intro_idx: int | None = None
        for idx, child in enumerate(children):
            if _is_heading1(child) and _is_intro_heading(child):
                intro_idx = idx
                break

        if intro_idx is None:
            body.insert(0, toc_node)
        else:
            insert_idx = len(children)
            for idx in range(intro_idx + 1, len(children)):
                if _is_heading1(children[idx]):
                    insert_idx = idx
                    break
            while insert_idx > intro_idx + 1 and _is_pagebreak_paragraph(children[insert_idx - 1]):
                insert_idx -= 1
            body.insert(insert_idx, toc_node)

        remove_pagebreak_paragraphs(body)
        apply_heading_after_spacing(body)
        _rewrite_paragraph_styles(body)
        styles_xml = tmp_path / "word" / "styles.xml"
        if styles_xml.exists():
            styles_tree = ET.parse(styles_xml)
            styles_root = styles_tree.getroot()
            _install_custom_word_styles(styles_root)
            styles_tree.write(styles_xml, encoding="utf-8", xml_declaration=True)
        tree.write(document_xml, encoding="utf-8", xml_declaration=True)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_docx:
            tmp_docx_path = Path(tmp_docx.name)
        try:
            with zipfile.ZipFile(tmp_docx_path, "w", zipfile.ZIP_DEFLATED) as zout:
                for file_path in tmp_path.rglob("*"):
                    if file_path.is_file():
                        zout.write(file_path, file_path.relative_to(tmp_path).as_posix())
            shutil.move(str(tmp_docx_path), docx_path)
        finally:
            if tmp_docx_path.exists():
                tmp_docx_path.unlink()



