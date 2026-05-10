"""参照ソース（URL / ファイル / 画像 / NotebookLM）の取り込みモジュール。

各参照を統一フォーマット {"label": ..., "kind": ..., "content": ...} で返す。
generator.py はこれを context として Gemini プロンプトに組み込む。
"""

from __future__ import annotations

import base64
import ipaddress
import mimetypes
import re
import socket
from pathlib import Path
from typing import TypedDict
from urllib.parse import urlparse

import requests


MAX_BYTES_PER_SOURCE = 200_000  # 1ソースあたり最大文字バイト数（誤った巨大ファイル対策）
USER_AGENT = "Mozilla/5.0 (compatible; BookMakerApp/1.0)"
REQUEST_TIMEOUT = 15


class Reference(TypedDict):
    label: str
    kind: str
    content: str


# ---------------------------------------------------------------------------
# URL
# ---------------------------------------------------------------------------


def _is_safe_url(url: str) -> bool:
    """SSRF 対策：内部 IP やプライベートネットワークを弾く。"""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return False
        host = parsed.hostname
        if not host:
            return False
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            try:
                resolved = socket.gethostbyname(host)
                ip = ipaddress.ip_address(resolved)
            except (socket.gaierror, ValueError):
                return False
        if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
            return False
        return True
    except Exception:
        return False


def fetch_url(url: str) -> Reference:
    url = url.strip()
    if not _is_safe_url(url):
        return {
            "label": url,
            "kind": "url",
            "content": "[取得失敗：URL が無効または内部ネットワーク]",
        }
    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        response.raise_for_status()
        text = _extract_main_text(response.text, url)
        text = text[:MAX_BYTES_PER_SOURCE]
        return {"label": url, "kind": "url", "content": text}
    except Exception as exc:  # noqa: BLE001
        return {
            "label": url,
            "kind": "url",
            "content": f"[取得失敗：{exc}]",
        }


def _extract_main_text(html: str, url: str) -> str:
    try:
        import trafilatura

        extracted = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=True,
            favor_recall=True,
        )
        if extracted:
            return extracted
    except Exception:
        pass
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()
        text = soup.get_text("\n", strip=True)
        return re.sub(r"\n{3,}", "\n\n", text)
    except Exception:
        return html


# ---------------------------------------------------------------------------
# ファイル（PDF / DOCX / MD / TXT / CSV）
# ---------------------------------------------------------------------------


def extract_file(path: Path, original_name: str | None = None) -> Reference:
    name = original_name or path.name
    ext = Path(name).suffix.lower()
    label = f"file: {name}"
    try:
        if ext == ".pdf":
            content = _extract_pdf(path)
        elif ext == ".docx":
            content = _extract_docx(path)
        elif ext in {".md", ".markdown", ".txt", ".csv", ".json", ".yml", ".yaml"}:
            content = path.read_text(encoding="utf-8", errors="replace")
        else:
            content = f"[未対応の拡張子：{ext}]"
        return {"label": label, "kind": "file", "content": content[:MAX_BYTES_PER_SOURCE]}
    except Exception as exc:  # noqa: BLE001
        return {"label": label, "kind": "file", "content": f"[読み込み失敗：{exc}]"}


def _extract_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    parts: list[str] = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
            parts.append(f"--- Page {i+1} ---\n{text.strip()}")
        except Exception as exc:  # noqa: BLE001
            parts.append(f"--- Page {i+1} ---\n[抽出失敗：{exc}]")
        if sum(len(p) for p in parts) > MAX_BYTES_PER_SOURCE:
            break
    return "\n\n".join(parts)


def _extract_docx(path: Path) -> str:
    from docx import Document

    doc = Document(str(path))
    parts: list[str] = []
    for p in doc.paragraphs:
        if p.text.strip():
            parts.append(p.text.strip())
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# 画像（Gemini Vision で説明テキスト生成）
# ---------------------------------------------------------------------------


def analyze_image(path: Path, original_name: str, api_key: str, model: str = "gemini-2.0-flash-exp") -> Reference:
    label = f"image: {original_name}"
    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        m = genai.GenerativeModel(model)
        mime, _ = mimetypes.guess_type(original_name)
        if not mime:
            mime = "image/png"
        with open(path, "rb") as fp:
            data = fp.read()
        prompt = (
            "この画像の内容を、書籍の素材として活用できる形で詳しく日本語で説明してください。"
            "図解の場合は構造、テキストの場合は内容、写真の場合は被写体と文脈を抽出してください。"
        )
        response = m.generate_content([
            prompt,
            {"mime_type": mime, "data": data},
        ])
        return {
            "label": label,
            "kind": "image",
            "content": (response.text or "").strip()[:MAX_BYTES_PER_SOURCE],
        }
    except Exception as exc:  # noqa: BLE001
        return {"label": label, "kind": "image", "content": f"[画像解析失敗：{exc}]"}


# ---------------------------------------------------------------------------
# NotebookLM 連携（公開ノートのコンテンツを URL 取得で吸い込む）
# ---------------------------------------------------------------------------


def fetch_notebooklm(url: str) -> Reference:
    """NotebookLM の共有 URL から取得を試みる。

    NotebookLM には公式 API が公開されていないため、共有 URL からの取得は
    Google 側のレンダリング仕様に依存する。動的ロード分は取得できない場合がある。
    取得できた範囲をテキストとして返す。
    """
    url = url.strip()
    label = f"notebooklm: {url}"
    if "notebooklm.google.com" not in url:
        return {
            "label": label,
            "kind": "notebooklm",
            "content": "[NotebookLM の URL ではありません]",
        }
    if not _is_safe_url(url):
        return {"label": label, "kind": "notebooklm", "content": "[URL が無効]"}
    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        response.raise_for_status()
        text = _extract_main_text(response.text, url)
        if not text or len(text) < 200:
            text = (
                "[NotebookLM はクライアントサイド・レンダリングのため、"
                "公開ノート本文を直接取得できない場合があります。"
                "代わりに NotebookLM 内で『エクスポート』機能で書き出した Markdown / PDF を"
                "ファイル参照としてアップロードしてください]"
            )
        return {"label": label, "kind": "notebooklm", "content": text[:MAX_BYTES_PER_SOURCE]}
    except Exception as exc:  # noqa: BLE001
        return {"label": label, "kind": "notebooklm", "content": f"[取得失敗：{exc}]"}


# ---------------------------------------------------------------------------
# 集約ヘルパ
# ---------------------------------------------------------------------------


def render_references_block(refs: list[Reference]) -> str:
    """参照を Gemini プロンプト用にフォーマット。"""
    if not refs:
        return ""
    lines = ["【参照ソース】"]
    for i, r in enumerate(refs, 1):
        lines.append(f"--- 参照 {i}: {r['kind']} | {r['label']} ---")
        lines.append(r["content"])
        lines.append("")
    lines.append("【参照ソース ここまで】")
    lines.append("")
    lines.append(
        "上記参照ソースの事実・固有名詞・数値・主張を本書の素材として活用してください。"
        "ただし参照ソースをそのままコピペするのではなく、本書の文脈と口調規範に合わせて"
        "再構築・要約・引用してください。"
    )
    return "\n".join(lines)
