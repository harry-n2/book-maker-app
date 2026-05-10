"""v7 専用 Pandoc reference-doc.docx を生成する。

Pandoc の標準 reference.docx を起点に、フォント・サイズ・色を
v7 ミニ実用書帯に最適化してカスタマイズする。

実行：
    python make_reference_doc.py

出力：
    templates/reference_v7.docx
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

import pypandoc

BASE = Path(__file__).resolve().parent
TEMPLATES = BASE / "templates"
DEFAULT_DOCX = TEMPLATES / "reference_default.docx"
V7_DOCX = TEMPLATES / "reference_v7.docx"

# Windows / Mac 双方で表示される無難な日本語フォント（フォールバック付き）
JP_FONT = "游ゴシック"   # Windows 標準・Mac は游ゴシック体（一致）
EN_FONT = "游ゴシック"   # 英数字も日本語に合わせる
CODE_FONT = "Consolas"   # コード用


def extract_default_reference() -> None:
    """Pandoc のデフォルト reference.docx を抽出する。"""
    pandoc_path = pypandoc.get_pandoc_path()
    DEFAULT_DOCX.parent.mkdir(parents=True, exist_ok=True)
    with open(DEFAULT_DOCX, "wb") as fp:
        result = subprocess.run(
            [pandoc_path, "--print-default-data-file=reference.docx"],
            stdout=fp,
            stderr=subprocess.PIPE,
            check=True,
        )
    print(f"[OK] extract: {DEFAULT_DOCX} ({DEFAULT_DOCX.stat().st_size} B)")


def _ensure_rpr(style) -> object:
    """style.element.rPr を確実に取得（無ければ作る）。"""
    el = style.element
    rPr = el.find(qn("w:rPr"))
    if rPr is None:
        rPr = OxmlElement("w:rPr")
        el.append(rPr)
    return rPr


def _set_font_complete(style, ascii_font: str, jp_font: str) -> None:
    """ASCII / EastAsia / hAnsi / cs すべてのフォント属性を設定する。"""
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


def style_set(
    doc,
    name: str,
    *,
    size_pt: float | None = None,
    bold: bool | None = None,
    color: str | None = None,
    ascii_font: str = EN_FONT,
    jp_font: str = JP_FONT,
) -> None:
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
    print(f"  [set] {name}: size={size_pt} bold={bold} font={jp_font} color={color}")


def build_v7_reference() -> None:
    if not DEFAULT_DOCX.exists():
        extract_default_reference()
    shutil.copyfile(DEFAULT_DOCX, V7_DOCX)
    doc = Document(str(V7_DOCX))

    print("[v7 専用テンプレ作成中]")
    style_set(doc, "Normal",         size_pt=11.0,                              color="222222")
    style_set(doc, "Body Text",      size_pt=11.0,                              color="222222")
    style_set(doc, "First Paragraph",size_pt=11.0,                              color="222222")
    style_set(doc, "Compact",        size_pt=11.0,                              color="222222")
    style_set(doc, "Title",          size_pt=28.0, bold=True,                   color="0F1A2E")
    style_set(doc, "Heading 1",      size_pt=22.0, bold=True,                   color="1E5BFF")
    style_set(doc, "Heading 2",      size_pt=17.0, bold=True,                   color="1840B8")
    style_set(doc, "Heading 3",      size_pt=14.0, bold=True,                   color="2A3340")
    style_set(doc, "Heading 4",      size_pt=12.5, bold=True,                   color="2A3340")
    style_set(doc, "Source Code",    size_pt=10.0, ascii_font=CODE_FONT, jp_font=CODE_FONT, color="333333")
    style_set(doc, "Block Text",     size_pt=11.0,                              color="555555")
    style_set(doc, "TOC Heading",    size_pt=18.0, bold=True,                   color="1E5BFF")
    style_set(doc, "Author",         size_pt=12.0,                              color="555555")

    doc.save(str(V7_DOCX))
    print(f"[OK] save: {V7_DOCX} ({V7_DOCX.stat().st_size} B)")


if __name__ == "__main__":
    build_v7_reference()
