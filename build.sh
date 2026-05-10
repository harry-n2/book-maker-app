#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
echo "================================================"
echo "Book Maker - 実行ファイル化（Mac / Linux）"
echo "================================================"
echo ""

echo "[1/3] PyInstaller をインストールしています..."
python -m pip install --user --quiet --upgrade pyinstaller pyinstaller-hooks-contrib

echo ""
echo "[2/3] 必要な依存をインストールしています..."
python -m pip install --user --quiet -r requirements.txt

echo ""
echo "[3/3] BookMaker をビルドしています（数分かかります）..."
python -m PyInstaller --noconfirm BookMaker.spec

echo ""
echo "================================================"
echo "ビルド成功！"
echo "  dist/BookMaker (Mac/Linux 実行可能ファイル)"
echo "================================================"
echo "ダブルクリック（または ./dist/BookMaker）で起動できます。"
