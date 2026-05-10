# 引き継ぎ書：Codex CLI（Book Maker App プロジェクト）

このファイル一つだけで、再起動後にプロジェクトを再開できるよう設計しています。
Codex CLI を起動した直後にこのファイル全文を読み込ませてください。

---

## 0. ファースト・リード（要約）

```
プロジェクト名：Book Maker App（Kindle 電子書籍 自動生成アプリ）
プロジェクトパス：C:\Users\naoya\myproject\book_maker_app
GitHub：https://github.com/harry-n2/book-maker-app
GitHub Releases：v1.0.1 公開済（BookMaker.exe 87.7MB）
Vercel 本番：https://bookmakerapp.vercel.app
最終 commit：b077c28（feat(icon): BookMaker.ico 追加）
最終 tag：v1.0.1
言語：日本語
著者：ハリー（営業25年・LP100枚＋・Kindle40冊＋・AIアプリ200本＋）
LINE：lin.ee/7qGC2YD
```

---

## 1. プロジェクト概要

ユーザーが 4〜5 ステップ入力するだけで Kindle KDP 入稿可能な電子書籍を自動生成する Web アプリ＋デスクトップアプリ。

### 配布形態
| 形態 | 場所 | 用途 |
|------|------|------|
| デスクトップ exe | `dist/BookMaker.exe` | エンドユーザー配布（v1.0.1 公開） |
| Web 版（Vercel） | https://bookmakerapp.vercel.app | インストール不要・60秒制限あり |
| ローカル Python | `python launcher.py` | 開発用 |

### 技術スタック
- FastAPI + Uvicorn（同期/非同期 Web フレームワーク）
- Google Gemini API（gemini-2.0-flash-exp）
- pypandoc-binary（Pandoc 同梱・MD→DOCX）
- python-docx / pypdf / trafilatura / Pillow
- PyInstaller（exe ビルド）

---

## 2. ファイル構成（Codex の @記法用）

```
book_maker_app/
├── app.py                        FastAPI エンドポイント（4 routes）
├── generator.py                  書籍生成コア
├── references.py                 参照素材取込
├── _resource.py                  環境別パス解決
├── launcher.py                   exe 起動エントリ
├── BookMaker.spec                PyInstaller 設定
├── BookMaker.ico                 アイコン（8サイズ ICO）
├── make_icon.py                  アイコン再生成
├── make_reference_doc.py         Pandoc reference-doc 再生成
├── build.bat / build.sh          exe ビルドスクリプト
├── requirements.txt              依存
├── vercel.json                   Vercel 設定
├── api/index.py                  Vercel ASGI エントリ
├── prompts/
│   ├── system.txt                voice.md v7.1 規範
│   ├── titles.txt                タイトル10選
│   ├── structure.txt             v7 構造（H1=4-5・H2=2-3）
│   ├── chapter.txt               章本文
│   ├── reference.txt             章末3層コピペ
│   ├── promotion.txt             宣伝
│   └── description.txt           Kindle 紹介文 720字
├── templates/
│   ├── index.html                メインUI
│   └── reference_v7.docx         Pandoc テンプレ
└── static/style.css / app.js
```

---

## 3. v7 仕様（書籍生成の基準）

### 章立て（厳守）
- H1：本編 4〜5章（はじめに・おわりに・宣伝はカウント外）
- H2：各章 2〜3節
- H3：各章合計 0〜2 個（任意配置・AIが判断）
- 章末ブロック（まとめ＋3層コピペ）は H2 にカウントしない

### 連結順
```
表紙（タイトル H1 + サブタイ H2 + 著者）
→ 目次（Pandoc 自動生成）
→ はじめに → 本編 第1〜N章 → おわりに → 宣伝
（Kindle紹介文は連結対象外・別ファイル）
```

### 文字数
- 本文：8,000〜15,000字
- リファレンス（コピペブロック）：4,000〜7,500字
- 合計：15,000〜22,500字（KDP ¥250〜¥500 / KU 帯）

---

## 4. 口調規範（voice.md v7.1）

### 必読リンク
```
@C:\Users\naoya\myproject\Obsidian link\my-engine\v8\x-posts\drafts\voice.md
```

### 厳守項目
- 地の文：丁寧調（です／ます）100%
- Scope A：ハリー述懐＝言い切り型OK（「正直に言わせてください」「気づいたんです」）
- Scope B：読者語りかけ＝丁寧語り掛け一択
- 命令形「〜しろ／〜してくれ／〜せよ」絶対禁止
- 「いかがでしたでしょうか」「皆さん、こんにちは」絶対禁止
- マークダウン強調記号「\*\*xxx\*\*」絶対禁止
- 「ぜひ」多用禁止（章あたり1回まで）
- 中流階級KW（年収／時間単価／組織／年商／キャリア／45歳の壁）各章最低1回
- 失敗談バンクA〜G を各章1つ（章間重複なし）
- 冒頭1行は voice.md の10型から選択

### 著者プロフィール
- 「ハリー」名義のみ
- X アカウント名（@…）は本文・著者プロフに**絶対記載しない**
- LINE: `lin.ee/7qGC2YD` のみ記載可

---

## 5. Codex CLI 再起動コマンド

### 起動直後にこれを投げる

```
@C:\Users\naoya\myproject\book_maker_app\_handoff_codex.md
を全文読み込んでください。

その上で、以下のいずれかを依頼します：
A. 機能追加：xxx を追加してほしい
B. バグ修正：xxx を調査して直してほしい
C. リリース v1.0.2 を作ってほしい
D. UI を改善してほしい
E. プロンプトをチューニングしてほしい
```

### よく使うリファレンス参照
```
@app.py                            FastAPI 4エンドポイント
@generator.py                      start_titles_job / continue_book_job
@_resource.py                      Vercel/PyInstaller/開発 全環境対応
@prompts/structure.txt             v7 構造プロンプト
@prompts/system.txt                voice.md 規範
@templates/index.html              UI 5ステップ
@static/app.js                     2段階通信ロジック
@my-engine/v8/x-posts/drafts/voice.md  口調規範 v7.1
```

### 一括ビルドコマンド
```bash
cd C:/Users/naoya/myproject/book_maker_app

# 起動
python launcher.py

# exe 再ビルド
build.bat   # Windows
./build.sh  # Mac/Linux

# アイコン・テンプレ再生成
python make_icon.py
python make_reference_doc.py
```

---

## 6. 編集時のガードレール

### 禁止事項
- API キーをコード／設定ファイル／commit に含めない
- 旧 `POST /generate` を復活させない（廃止済み）
- prompts/ のテンプレを書き換えるときは voice.md v7.1 規約必須
- v6 教科書帯（H1=10/H2=58/H3=34/45,000字）の凍結ファイル（cover-app-business 配下）は触らない
- ジョブ書き込み先を `_resource.writable_root()` 経由なしで直接決め打ちしない
- マークダウン強調記号「\*\*xxx\*\*」を新規に入れない（既存 0 件運用）
- X アカウント名を本文・著者プロフに記載しない

### 推奨事項
- 既存ファイル編集前に必ず Read / @ で読み込む
- 動作変更時は launcher.py で起動して curl で動作確認
- Vercel 反映確認は10秒待って GET /
- 大きな仕様変更時は v7 規格を破壊しないよう `_validate_structure()` の検証ロジック維持

---

## 7. Git / リリース 操作

### 最新状態の取得
```bash
git pull
git log --oneline -10
git tag -l    # v1.0.0 / v1.0.1
gh release list
```

### 新リリース作成（v1.0.2 例）
```bash
# 1. commit & push
git add -A
git commit -m "feat(xxx): ..."
git push

# 2. tag
git tag -a v1.0.2 -m "v1.0.2：..."
git push origin v1.0.2

# 3. exe 再ビルド
build.bat

# 4. Releases 公開
gh release create v1.0.2 --title "v1.0.2 — ..." --notes-file CHANGELOG.md --latest
gh release upload v1.0.2 dist/BookMaker.exe
```

### Vercel 自動デプロイ
GitHub `main` push → Vercel 10秒で自動再デプロイ。手動操作不要。

---

## 8. 既知の落とし穴（実証済み）

| 落とし穴 | 検知方法 | 対策 |
|---------|---------|------|
| Vercel 60秒タイムアウト | `/confirm-title` で本編生成中に504 | ローカル運用前提 |
| Vercel ファイルシステム読取専用 | mkdir で500 | `_resource.is_serverless()` で `/tmp` フォールバック |
| `_resource.writable_root()` を使わず直接 mkdir | サーバー起動時 500 | `_resource.jobs_dir()` 経由必須 |
| Vercel リクエストボディ4.5MB上限 | 21ファイル送信で500 | exe 経由推奨 |
| `google.generativeai` deprecated警告 | FutureWarning | 動作影響なし。将来 `google-genai` 移行 |
| Windows Defender 警告 | exe 初回起動 | コード署名なしのため・「詳細情報→実行」案内 |
| Pandoc reference_v7.docx 不在 | DOCX のスタイル崩れ | `convert_to_docx()` で存在チェック付き |
| ブラウザリロードで job_id 消失 | UI 状態リセット | サーバー側 JOB_STATE 保持・localStorage 復元可 |

---

## 9. 残タスク・推奨ロードマップ

### 短期（1〜2時間）
- Mac.app 版追加
- README にバッジ／スクリーンショット
- コンソール窓非表示化（`console=False`）

### 中期（半日〜1日）
- インストーラー化（Inno Setup）
- `google.generativeai` → `google-genai` 移行
- 多端末同期（Supabase）

### 長期（複数日）
- コード署名（年¥30,000）
- Render 並行デプロイ
- 挿絵対応

---

## 10. 関連プロジェクト

### v6 教科書帯（凍結・参考）
```
C:\Users\naoya\myproject\Obsidian link\kindle project\cover-app-business\
├── 01_design/book_style_standard.md  v6/v7 併存基準書
├── 01_design/book_spec.md            v3 文字数ガイド
├── 02_skills/book_writer.md          v3 ライター
└── 04_output/kindle publish/         v6 凍結書籍
```

### my-engine（口調規範）
```
C:\Users\naoya\myproject\Obsidian link\my-engine\
└── v8/x-posts/drafts/voice.md        v7.1 規範（必読）
```

---

## 11. 完成済み成果物の URL 一覧

| 種別 | URL |
|------|-----|
| GitHub リポジトリ | https://github.com/harry-n2/book-maker-app |
| GitHub Releases（最新） | https://github.com/harry-n2/book-maker-app/releases/latest |
| BookMaker.exe 直接DL | https://github.com/harry-n2/book-maker-app/releases/download/v1.0.1/BookMaker.exe |
| Vercel 本番 | https://bookmakerapp.vercel.app |
| Vercel Inspect | https://vercel.com/harry-n2/book_maker_app |

---

最終確認：このファイルを全文読み込んだ時点で、Codex CLI は本プロジェクトの全コンテキストを保持できているはずです。
