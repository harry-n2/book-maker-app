"""ローカル・ライブ検証（実Gemini呼び出し）。キーは表示しない。

キー取得順: 環境変数 GEMINI_API_KEY → 同フォルダ .localkey ファイル。
実行: python smoke_test_live.py
- タイトル10選を実生成し、モデルID・件数・サンプル1件だけ表示する。
- 失敗時はエラー種別のみ表示（キーは絶対に出力しない）。
"""
from __future__ import annotations

import os
from pathlib import Path


def _load_key() -> str:
    k = os.environ.get("GEMINI_API_KEY", "").strip()
    if k:
        return k
    f = Path(__file__).with_name(".localkey")
    if f.exists():
        return f.read_text(encoding="utf-8").strip()
    return ""


def main() -> int:
    key = _load_key()
    if not key:
        print("NG: APIキー未設定（.localkey も環境変数も無し）。検証を中止。")
        return 2

    from generator import BookConfig, DEFAULT_MODEL, generate_titles, resolve_model

    cfg = BookConfig(
        theme="AIで副業を仕組み化して月10万円を安定させる実践ガイド",
        target_layer="副業1〜3年目の30代会社員（実績はあるが伸び悩んでいる方）",
        author="テスト著者",
        api_key=key,
        profile_author_bio="中小企業のWeb集客を10年支援。",
        profile_tone="落ち着いた実務家の口調。",
        profile_target_keywords=["副業", "AI活用", "仕組み化"],
    )
    print(f"使用モデル: {resolve_model(cfg.model)}  (DEFAULT={DEFAULT_MODEL})")
    try:
        cands = generate_titles(cfg)
    except Exception as exc:  # noqa: BLE001
        print(f"NG: 生成失敗 = {type(exc).__name__}: {exc}")
        return 1

    n = len(cands or [])
    print(f"OK: タイトル候補 {n} 件を実生成")
    if n:
        c0 = cands[0]
        print(f"サンプル先頭: title={c0.get('title')!r} / subtitle={c0.get('subtitle')!r}")
    return 0 if n else 1


if __name__ == "__main__":
    raise SystemExit(main())
