@echo off
chcp 65001 >nul
cd /d %~dp0
echo ================================================
echo Book Maker - 実行ファイル化（Windows）
echo ================================================
echo.

echo [1/3] PyInstaller をインストールしています...
python -m pip install --user --quiet --upgrade pyinstaller pyinstaller-hooks-contrib
if errorlevel 1 (
  echo [ERROR] pyinstaller のインストールに失敗しました。
  pause
  exit /b 1
)

echo.
echo [2/3] 必要な依存をインストールしています...
python -m pip install --user --quiet -r requirements.txt
if errorlevel 1 (
  echo [ERROR] 依存パッケージのインストールに失敗しました。
  pause
  exit /b 1
)

echo.
echo [3/3] BookMaker.exe をビルドしています（数分かかります）...
python -m PyInstaller --noconfirm BookMaker.spec
if errorlevel 1 (
  echo [ERROR] ビルドに失敗しました。
  pause
  exit /b 1
)

echo.
echo ================================================
echo ビルド成功！
echo   dist\BookMaker.exe
echo ================================================
echo dist\BookMaker.exe をダブルクリックすると、
echo Book Maker が起動してブラウザが開きます。
echo.
pause
