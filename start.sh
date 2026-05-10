#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
echo "========================================"
echo "Book Maker - 起動準備"
echo "========================================"
echo ""
echo "必要なライブラリをインストールしています..."
python -m pip install --user -q -r requirements.txt
echo ""
echo "サーバーを起動します。ブラウザで http://127.0.0.1:8765 を開いてください。"
echo "（終了するには Ctrl+C を押してください）"
echo ""
python app.py
