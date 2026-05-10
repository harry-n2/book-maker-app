"""Book Maker デスクトップ起動スクリプト。

ダブルクリックで起動 → uvicorn をバックグラウンドで立ち上げ → ブラウザを自動で開く。

PyInstaller でビルド済みの .exe では、sys._MEIPASS から同梱リソースを参照する。
開発環境（python launcher.py）では本ディレクトリから直接動作。
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

# PyInstaller 環境では _MEIPASS を sys.path に通す
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    sys.path.insert(0, sys._MEIPASS)  # type: ignore[attr-defined]
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import _resource  # noqa: E402


HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def find_free_port(start: int = DEFAULT_PORT, max_tries: int = 20) -> int:
    """未使用ポートを探す（既存プロセスとの衝突回避）。"""
    for offset in range(max_tries):
        port = start + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((HOST, port))
                return port
            except OSError:
                continue
    return start


def open_browser_when_ready(url: str, timeout: float = 30.0) -> None:
    """uvicorn が応答するようになってからブラウザを開く。"""
    import urllib.request

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                if resp.status == 200:
                    break
        except Exception:
            time.sleep(0.5)
    try:
        webbrowser.open_new(url)
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] ブラウザの起動に失敗しました：{exc}")
        print(f"  手動で {url} を開いてください。")


def main() -> int:
    port = find_free_port()
    url = f"http://{HOST}:{port}"

    print("=" * 60)
    print("  Book Maker - 起動中")
    print("=" * 60)
    print(f"  URL : {url}")
    print(f"  作業フォルダ : {_resource.writable_root()}")
    print(f"  終了するにはこのウィンドウを閉じてください")
    print("=" * 60)
    print()

    # ブラウザ起動を別スレッドで（uvicorn は同期で起動）
    threading.Thread(
        target=open_browser_when_ready, args=(url,), daemon=True
    ).start()

    # 同梱リソースから FastAPI アプリを読み込む
    import uvicorn

    os.environ["PORT"] = str(port)
    uvicorn.run("app:app", host=HOST, port=port, log_level="info", reload=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
