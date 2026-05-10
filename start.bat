@echo off
chcp 65001 >nul
cd /d %~dp0
echo ========================================
echo Book Maker - 起動準備
echo ========================================
echo.
echo 必要なライブラリをインストールしています...
python -m pip install --user -q -r requirements.txt
if errorlevel 1 (
  echo インストールに失敗しました。Python が入っていない可能性があります。
  pause
  exit /b 1
)
echo.
echo サーバーを起動します。ブラウザで http://127.0.0.1:8765 を開いてください。
echo （終了するには このウィンドウで Ctrl+C を押してください）
echo.
python app.py
pause
