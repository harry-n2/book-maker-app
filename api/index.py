"""Vercel エントリポイント。FastAPI app を ASGI として公開する。

注意：Vercel Functions は実行時間とファイル書き込みに制約があるため、
本アプリの長時間ジョブ（書籍1冊5〜10分）はそのままでは完走しない。
完全動作には Render / Railway 等の長時間実行可能なホスティングを推奨。
"""

import sys
from pathlib import Path

# /api/index.py から見て親ディレクトリを sys.path に追加
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app  # noqa: E402

# Vercel は ASGI の `app` を自動検出してハンドラとして使う
