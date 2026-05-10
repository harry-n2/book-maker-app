"""PyInstaller 対応のリソースパス解決ユーティリティ。

PyInstaller --onefile では、同梱されたデータファイルは
sys._MEIPASS（一時展開先）配下にある。通常実行時は __file__ の親ディレクトリ。
両方の環境で同一インターフェースで動くよう抽象化する。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    """PyInstaller でバンドルされた exe として実行中か。"""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def resource_root() -> Path:
    """同梱リソース（テンプレ・プロンプト・静的ファイル）のルート。"""
    if is_frozen():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


def writable_root() -> Path:
    """書き込み可能なディレクトリ（jobs/ など）。

    PyInstaller --onefile では実行時の _MEIPASS は temp 配下で
    プロセス終了時に消えるため、ジョブの永続化には別ディレクトリを使う。

    優先順位：
    1. 環境変数 BOOK_MAKER_HOME
    2. exe 実行時：exe と同じディレクトリの BookMaker_jobs/
    3. それ以外：__file__ の親ディレクトリ（開発環境）
    """
    env = os.environ.get("BOOK_MAKER_HOME")
    if env:
        p = Path(env)
        p.mkdir(parents=True, exist_ok=True)
        return p
    if is_frozen():
        exe_dir = Path(sys.executable).resolve().parent
        p = exe_dir / "BookMaker_jobs"
        p.mkdir(parents=True, exist_ok=True)
        return p
    return Path(__file__).resolve().parent


def resource(*parts: str) -> Path:
    """同梱リソースへのパス。例：resource('templates', 'index.html')"""
    return resource_root().joinpath(*parts)


def jobs_dir() -> Path:
    """ジョブ出力先（書き込み可能）。"""
    p = writable_root() / "jobs"
    p.mkdir(parents=True, exist_ok=True)
    return p
