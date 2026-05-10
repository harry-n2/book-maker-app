"""PyInstaller / Vercel / 開発環境すべてに対応するリソース解決ユーティリティ。

リソース解決：
  - resource_root() ── 同梱データ（テンプレ・プロンプト・静的アセット）のルート
  - resource(*parts) ── 同梱データへのパス
  - writable_root() ── 書き込み可能なディレクトリ（jobs/ など）
  - jobs_dir() ── ジョブ出力先

PyInstaller --onefile：sys._MEIPASS 配下に展開、ジョブは exe と同階層
Vercel / Lambda：書き込み不可なので /tmp にフォールバック
開発環境：__file__ の親ディレクトリ
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


def is_frozen() -> bool:
    """PyInstaller でバンドルされた exe として実行中か。"""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def is_serverless() -> bool:
    """Vercel / AWS Lambda などサーバーレス環境か。"""
    return bool(
        os.environ.get("VERCEL")
        or os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
        or os.environ.get("LAMBDA_TASK_ROOT")
    )


def resource_root() -> Path:
    """同梱リソース（テンプレ・プロンプト・静的ファイル）のルート。"""
    if is_frozen():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


def resource(*parts: str) -> Path:
    """同梱リソースへのパス。例：resource('templates', 'index.html')"""
    return resource_root().joinpath(*parts)


def _try_writable(p: Path) -> bool:
    """指定ディレクトリが書き込み可能か（書き込みテストして判定）。"""
    try:
        p.mkdir(parents=True, exist_ok=True)
        test = p / ".write_test"
        test.write_text("ok", encoding="utf-8")
        test.unlink()
        return True
    except (OSError, PermissionError):
        return False


def writable_root() -> Path:
    """書き込み可能なディレクトリを優先順で探して返す。

    優先順位：
    1. 環境変数 BOOK_MAKER_HOME
    2. PyInstaller exe 環境：exe と同階層の BookMaker_jobs/
    3. Vercel / Lambda 環境：/tmp/book_maker
    4. 開発環境：__file__ の親ディレクトリ
    5. フォールバック：システム tempdir / book_maker
    """
    candidates: list[Path | None] = []
    env = os.environ.get("BOOK_MAKER_HOME")
    if env:
        candidates.append(Path(env))
    if is_frozen():
        candidates.append(Path(sys.executable).resolve().parent / "BookMaker_jobs")
    if is_serverless():
        candidates.append(Path("/tmp/book_maker"))
    candidates.append(Path(__file__).resolve().parent)
    candidates.append(Path(tempfile.gettempdir()) / "book_maker")

    for c in candidates:
        if c is None:
            continue
        if _try_writable(c):
            return c
    # 最終手段：tempdir 直下
    return Path(tempfile.gettempdir())


def jobs_dir() -> Path:
    """ジョブ出力先（書き込み可能）。"""
    p = writable_root() / "jobs"
    try:
        p.mkdir(parents=True, exist_ok=True)
    except (OSError, PermissionError):
        # writable_root も書けない場合のフォールバック
        p = Path(tempfile.gettempdir()) / "book_maker_jobs"
        p.mkdir(parents=True, exist_ok=True)
    return p
