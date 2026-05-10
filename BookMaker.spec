# PyInstaller spec for Book Maker (--onefile, GUI/console hybrid)
#
# 使い方：
#   python -m pip install --user pyinstaller
#   pyinstaller BookMaker.spec
# 出力：dist/BookMaker.exe（Windows）／dist/BookMaker（Mac/Linux）

import sys
from pathlib import Path

# Pandoc バイナリ（pypandoc-binary に同梱）を一緒にバンドル
try:
    import pypandoc
    pandoc_path = pypandoc.get_pandoc_path()
except Exception:
    pandoc_path = None

block_cipher = None

# 同梱データ（テンプレ・プロンプト・静的アセット）
datas = [
    ("prompts", "prompts"),
    ("templates", "templates"),
    ("static", "static"),
]

# Pandoc バイナリ
binaries = []
if pandoc_path and Path(pandoc_path).exists():
    pandoc_dir = Path(pandoc_path).parent
    binaries.append((str(Path(pandoc_path)), "pypandoc/files"))

a = Analysis(
    ["launcher.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "fastapi",
        "starlette.routing",
        "google.generativeai",
        "google.ai.generativelanguage",
        "pypandoc",
        "docx",
        "pypdf",
        "trafilatura",
        "bs4",
        "_resource",
        "app",
        "generator",
        "references",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="BookMaker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # 起動ログ確認のため True（後で False に切替可）
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
