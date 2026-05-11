"""Pandoc reference-doc.docx を生成する。

Pandoc の標準 reference.docx を起点に、フォント・サイズ・色を v7/v8 に最適化する。

- v7：ミニ実用書帯の基本スタイル
- v8：v7 にコピペ枠・ケーススタディBOX・比較表ヘッダの強調スタイルを追加（v1.2）

実行：
    python make_reference_doc.py

出力：
    templates/reference_v7.docx
    templates/reference_v8.docx
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt

import pypandoc

BASE = Path(__file__).resolve().parent
TEMPLATES = BASE / "templates"
DEFAULT_DOCX = TEMPLATES / "reference_default.docx"
V7_DOCX = TEMPLATES / "reference_v7.docx"
V8_DOCX = TEMPLATES / "reference_v8.docx"

JP_FONT = "游ゴシック"
EN_FONT = "游ゴシック"
CODE_FONT = "Consolas"


def extract_default_reference() -> None:
    pandoc_path = pypandoc.get_pandoc_path()
    DEFAULT_DOCX.parent.mkdir(parents=True, exist_ok=True)
    with open(DEFAULT_DOCX, "wb") as fp:
        subprocess.run(
            [pandoc_path, "--print-default-data-file=reference.docx"],
            stdout=fp,
            stderr=subprocess.PIPE,
            check=True,
        )
    print(f"[OK] extract: {DEFAULT_DOCX} ({DEFAULT_DOCX.stat().st_size} B)")


def _ensure_rpr(style) -> object:
    el = style.element
    rPr = el.find(qn("w:rPr"))
    if rPr is None:
        rPr = OxmlElement("w:rPr")
        el.append(rPr)
    return rPr


def _ensure_ppr(style) -> object:
    el = style.element
    pPr = el.find(qn("w:pPr"))
    if pPr is None:
        pPr = OxmlElement("w:pPr")
        el.insert(0, pPr)
    return pPr


def _set_font_complete(style, ascii_font: str, jp_font: str) -> None:
    rPr = _ensure_rpr(style)
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.insert(0, rFonts)
    rFonts.set(qn("w:ascii"), ascii_font)
    rFonts.set(qn("w:hAnsi"), ascii_font)
    rFonts.set(qn("w:eastAsia"), jp_font)
    rFonts.set(qn("w:cs"), ascii_font)


def _set_color(style, color_rgb: str) -> None:
    rPr = _ensure_rpr(style)
    color = rPr.find(qn("w:color"))
    if color is None:
        color = OxmlElement("w:color")
        rPr.append(color)
    color.set(qn("w:val"), color_rgb)


def _set_paragraph_shading(style, fill_rgb: str) -> None:
    """段落に背景色を設定（w:pPr > w:shd）。"""
    pPr = _ensure_ppr(style)
    shd = pPr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        pPr.append(shd)
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill_rgb)


def _set_paragraph_left_border(style, color_rgb: str, size: int = 24) -> None:
    """段落の左に縦線を設定（w:pPr > w:pBdr > w:left）。size は 1/8 pt 単位。"""
    pPr = _ensure_ppr(style)
    pBdr = pPr.find(qn("w:pBdr"))
    if pBdr is None:
        pBdr = OxmlElement("w:pBdr")
        pPr.append(pBdr)
    for tag in ("left",):
        bd = pBdr.find(qn(f"w:{tag}"))
        if bd is None:
            bd = OxmlElement(f"w:{tag}")
            pBdr.append(bd)
        bd.set(qn("w:val"), "single")
        bd.set(qn("w:sz"), str(size))
        bd.set(qn("w:space"), "8")
        bd.set(qn("w:color"), color_rgb)


def _ensure_style(doc, name: str, style_type=WD_STYLE_TYPE.PARAGRAPH):
    """スタイルが無ければ新規作成して返す。"""
    try:
        return doc.styles[name]
    except KeyError:
        return doc.styles.add_style(name, style_type)


def style_set(
    doc,
    name: str,
    *,
    size_pt: float | None = None,
    bold: bool | None = None,
    color: str | None = None,
    ascii_font: str = EN_FONT,
    jp_font: str = JP_FONT,
    shading_fill: str | None = None,
    left_border: str | None = None,
    create_if_missing: bool = False,
    style_type=WD_STYLE_TYPE.PARAGRAPH,
) -> None:
    if create_if_missing:
        style = _ensure_style(doc, name, style_type)
    else:
        try:
            style = doc.styles[name]
        except KeyError:
            print(f"  [skip] スタイル未定義: {name}")
            return
    if size_pt is not None:
        style.font.size = Pt(size_pt)
    if bold is not None:
        style.font.bold = bold
    if color:
        _set_color(style, color)
    _set_font_complete(style, ascii_font, jp_font)
    if shading_fill:
        _set_paragraph_shading(style, shading_fill)
    if left_border:
        _set_paragraph_left_border(style, left_border)
    extras = []
    if shading_fill:
        extras.append(f"shading={shading_fill}")
    if left_border:
        extras.append(f"left-border={left_border}")
    extra_str = (" " + " ".join(extras)) if extras else ""
    print(f"  [set] {name}: size={size_pt} bold={bold} font={jp_font} color={color}{extra_str}")


def _apply_v7_base(doc) -> None:
    """v7 / v8 共通の基本スタイル設定。"""
    style_set(doc, "Normal",         size_pt=11.0,                              color="222222")
    style_set(doc, "Body Text",      size_pt=11.0,                              color="222222")
    style_set(doc, "First Paragraph",size_pt=11.0,                              color="222222")
    style_set(doc, "Compact",        size_pt=11.0,                              color="222222")
    style_set(doc, "Title",          size_pt=28.0, bold=True,                   color="0F1A2E")
    style_set(doc, "Heading 1",      size_pt=22.0, bold=True,                   color="1E5BFF")
    style_set(doc, "Heading 2",      size_pt=17.0, bold=True,                   color="1840B8")
    style_set(doc, "Heading 3",      size_pt=14.0, bold=True,                   color="2A3340")
    style_set(doc, "Heading 4",      size_pt=12.5, bold=True,                   color="2A3340")
    style_set(doc, "Source Code",    size_pt=10.0, ascii_font=CODE_FONT, jp_font=CODE_FONT, color="333333", create_if_missing=True)
    style_set(doc, "Verbatim Char",   size_pt=10.0, ascii_font=CODE_FONT, jp_font=CODE_FONT, color="333333", create_if_missing=True, style_type=WD_STYLE_TYPE.CHARACTER)
    style_set(doc, "Block Text",     size_pt=11.0,                              color="555555")
    style_set(doc, "TOC Heading",    size_pt=18.0, bold=True,                   color="1E5BFF")
    style_set(doc, "Author",         size_pt=12.0,                              color="555555")


def build_v7_reference() -> None:
    if not DEFAULT_DOCX.exists():
        extract_default_reference()
    shutil.copyfile(DEFAULT_DOCX, V7_DOCX)
    doc = Document(str(V7_DOCX))
    print("[v7 専用テンプレ作成中]")
    _apply_v7_base(doc)
    doc.save(str(V7_DOCX))
    print(f"[OK] save: {V7_DOCX} ({V7_DOCX.stat().st_size} B)")


def build_v8_reference() -> None:
    """v7 + 視認性向上スタイル（コピペ枠・ケーススタディBOX・比較表ヘッダ）。"""
    if not DEFAULT_DOCX.exists():
        extract_default_reference()
    shutil.copyfile(DEFAULT_DOCX, V8_DOCX)
    doc = Document(str(V8_DOCX))
    print("[v8 視認性向上テンプレ作成中]")
    _apply_v7_base(doc)

    # コピペ枠（Source Code ＝ コードブロック）に薄黄背景＋左にアクセント線
    style_set(
        doc,
        "Source Code",
        size_pt=10.0,
        ascii_font=CODE_FONT,
        jp_font=CODE_FONT,
        color="2A3340",
        shading_fill="FFF8E1",
        left_border="F3C244",
        create_if_missing=True,
    )
    # ケーススタディBOX（Block Text ＝ 引用ブロック）に薄青背景＋左に青ボーダー
    style_set(
        doc,
        "Block Text",
        size_pt=11.0,
        color="2A3340",
        shading_fill="EAF0FF",
        left_border="1E5BFF",
    )

    doc.save(str(V8_DOCX))
    print(f"[OK] save: {V8_DOCX} ({V8_DOCX.stat().st_size} B)")


if __name__ == "__main__":
    build_v7_reference()
    build_v8_reference()
