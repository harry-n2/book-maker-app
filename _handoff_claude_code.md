# 引き継ぎ書：Claude Code（Book Maker App プロジェクト）

このファイル一つだけで、再起動後にプロジェクトを再開できるよう設計しています。
Claude Code を起動した直後にこのファイル全文を読み込ませてください。

---

## 0. ファースト・リード（要約）

```
プロジェクト名：Book Maker App（Kindle 電子書籍 自動生成アプリ）
プロジェクトパス：C:\Users\naoya\myproject\book_maker_app
GitHub：https://github.com/harry-n2/book-maker-app
GitHub Releases：v1.0.1 公開済（BookMaker.exe 87.7MB）
Vercel 本番：https://bookmakerapp.vercel.app
最終 commit：b077c28（feat(icon): BookMaker.ico を追加）
最終 tag：v1.0.1
現在の状態：完成・公開済・運用フェーズ

著者情報：
- ハリー（営業25年・LP100枚＋・Kindle40冊＋・AIアプリ200本＋）
- LINE: lin.ee/7qGC2YD
- X アカウント名は記載しない（プロジェクト規約）
```

---

## 1. プロジェクト全体像

### 目的
ユーザー（AIリテラシー低い読者層）がブラウザまたは exe ダブルクリックで起動し、4〜5ステップ入力するだけで Kindle KDP 入稿可能な電子書籍（Word ファイル）を生成する。

### 配布形態
| 形態 | URL／場所 | 用途 |
|------|---------|------|
| デスクトップ exe | `dist/BookMaker.exe`（87.7MB） | エンドユーザー配布・GitHub Releases v1.0.1 |
| Web 版（Vercel） | https://bookmakerapp.vercel.app | インストール不要・60秒制限あり |
| ローカル Python | `python launcher.py` | 開発用 |

### 技術スタック
- FastAPI + Uvicorn（Web フレームワーク）
- Google Gemini API（gemini-2.0-flash-exp・無料枠 1日1,500req）
- pypandoc-binary（Pandoc 同梱・MD→DOCX 変換）
- python-docx（DOCX 操作）
- pypdf / trafilatura / Pillow（参照素材取り込み）
- PyInstaller（exe ビルド）

---

## 2. 完成済み機能（v1.0.1 時点）

### 2-1. 5ステップ UI
1. テーマ入力
2. 読者層選択（5択）
3. 著者名入力
4. 参照素材（URL・ファイル10個・画像10個・NotebookLM）
5. Gemini API キー（ユーザー入力・サーバー保存なし）

### 2-2. 2段階UX（タイトル10選 → ユーザー選択 → 本編）
- `POST /generate-titles`：タイトル候補10選を生成（30〜60秒）
- 10カードをラジオで表示・1つ選択
- `POST /confirm-title/{job_id}`：選択 index を送信→本編生成バックグラウンド開始

### 2-3. 章立て（v7 ミニ実用書帯）
- H1：本編4〜5章（はじめに・おわりに・宣伝はカウント外）
- H2：各章 2〜3節
- H3：各章合計 0〜2 個（任意配置・AIが判断）
- 章末ブロック（まとめ＋3層コピペ）は H2 にカウントせず独立

### 2-4. 出力（5ファイル）
- `book_full.md`（Markdown）
- `book_full.docx`（Word・KDP 入稿可）
- `title_candidates.md`（10候補一覧）
- `book_description.md`（KDP紹介文 720字）
- `book_for_notebooklm.md`（NotebookLM 取込用）

### 2-5. デスクトップアプリ化
- `launcher.py`：未使用ポート自動探索＋ブラウザ自動起動
- `BookMaker.spec`：PyInstaller 設定（datas／binaries／icon）
- `_resource.py`：PyInstaller _MEIPASS / Vercel /tmp / 開発環境すべて対応
- `BookMaker.ico`：青系本アイコン（8サイズ ICO）

### 2-6. 関連基準ファイル（別プロジェクト・参照のみ）
- `C:\Users\naoya\myproject\Obsidian link\kindle project\cover-app-business\01_design\book_style_standard.md`：v6（教科書）/ v7（ミニ実用書）併存基準書
- `C:\Users\naoya\myproject\Obsidian link\my-engine\v8\x-posts\drafts\voice.md`：口調規範 v7.1（必読）

---

## 3. ファイル構成

```
book_maker_app/
├── app.py                        FastAPI エンドポイント（4 routes）
├── generator.py                  書籍生成コア（start_titles_job / continue_book_job）
├── references.py                 URL/ファイル/画像/NotebookLM 取込
├── _resource.py                  PyInstaller / Vercel / 開発 全環境対応リソース解決
├── launcher.py                   デスクトップ起動エントリ
├── BookMaker.spec                PyInstaller 設定
├── BookMaker.ico / BookMaker.png アイコン（256px）
├── make_icon.py                  アイコン再生成スクリプト
├── make_reference_doc.py         Pandoc reference-doc 再生成スクリプト
├── build.bat / build.sh          exe ビルド自動化
├── start.bat / start.sh          開発時起動スクリプト
├── requirements.txt              依存パッケージ
├── vercel.json                   Vercel 設定（maxDuration: 60）
├── api/index.py                  Vercel エントリ（ASGI エクスポート）
├── README.md                     使い方・トラブルシューティング
├── prompts/
│   ├── system.txt                共通システムプロンプト（voice.md v7.1 規範）
│   ├── titles.txt                タイトル10選プロンプト
│   ├── structure.txt             構造（H1/H2/H3）プロンプト ★v7仕様
│   ├── chapter.txt               章本文プロンプト
│   ├── reference.txt             章末3層コピペプロンプト
│   ├── promotion.txt             宣伝セクションプロンプト
│   └── description.txt           Kindle 紹介文（720字）プロンプト
├── templates/
│   ├── index.html                メインUI
│   ├── reference_v7.docx         Pandoc reference-doc（v7 専用テンプレ）
│   └── reference_default.docx    Pandoc 標準（再生成可・gitignore）
├── static/
│   ├── style.css                 スタイル
│   └── app.js                    画面制御（2段階通信ロジック）
├── jobs/                         開発時のジョブ出力（gitignore）
├── BookMaker_jobs/               exe 実行時のジョブ出力（gitignore）
├── build/, dist/                 PyInstaller 中間・成果物（gitignore）
├── _handoff_claude_code.md       本ファイル
├── _handoff_codex.md             Codex 向け引き継ぎ書
└── _handoff_antigravity.md       Antigravity 向け引き継ぎ書
```

---

## 4. 環境セットアップ（再起動時）

### 4-1. 既存環境を確認
```bash
# Python バージョン
python --version    # 3.12 以上推奨（実装環境は 3.14.4）

# 依存パッケージ
python -c "import fastapi, uvicorn, google.generativeai, pypandoc, docx, pypdf; print('all OK')"

# Pandoc
python -c "import pypandoc; print(pypandoc.get_pandoc_version())"
```

### 4-2. 不足パッケージのインストール
```bash
cd "C:/Users/naoya/myproject/book_maker_app"
python -m pip install --user -r requirements.txt
```

### 4-3. ローカル起動
```bash
python launcher.py
# → http://127.0.0.1:8765 が自動でブラウザに開く
```

または開発用：
```bash
python app.py
```

### 4-4. exe ビルド（必要時）
```bash
build.bat   # Windows
./build.sh  # Mac/Linux
# 成果物：dist/BookMaker.exe
```

---

## 5. Git / リリース 操作

### 5-1. 最新状態の取得
```bash
git pull
git log --oneline -10
git tag -l    # v1.0.0 / v1.0.1
```

### 5-2. 新リリース作成（v1.0.2 例）
```bash
# 1. 変更を commit & push
git add -A
git commit -m "feat(xxx): ..."
git push

# 2. タグ作成
git tag -a v1.0.2 -m "v1.0.2：..."
git push origin v1.0.2

# 3. exe 再ビルド
build.bat

# 4. Releases 作成＋アセット公開
gh release create v1.0.2 --title "v1.0.2 — ..." --notes "..." --latest
gh release upload v1.0.2 "dist/BookMaker.exe"
```

### 5-3. Vercel 自動デプロイ
GitHub の `main` に push すると自動的に Vercel が再デプロイ（10秒程度）。手動再デプロイは不要。

---

## 6. 絶対ルール（プロジェクト規約）

### 6-1. voice.md v7.1 厳守
書籍内容を編集する場合は以下を必ず守る：
- 地の文：丁寧調（です／ます）100%
- Scope A（著者述懐）：言い切り型OK
- Scope B（読者語りかけ）：丁寧語り掛け一択
- 命令形「〜しろ／〜してくれ」絶対禁止
- 「いかがでしたでしょうか」「皆さん、こんにちは」絶対禁止
- マークダウン強調記号「\*\*xxx\*\*」絶対禁止
- 中流階級KW（年収／時間単価／組織／年商／キャリア／45歳の壁）各章最低1回
- 失敗談バンクA〜G を各章1つ（章間重複なし）
- 冒頭1行は voice.md の10型から選択

### 6-2. 章立て v7 厳守
- H1：本編4〜5章
- H2：各章 2〜3
- H3：各章合計 0〜2
- 章末ブロックは H2 にカウントしない

### 6-3. 著者プロフィール
- 「ハリー」名義のみ
- X アカウント名（@…）は本文・著者プロフに**絶対記載しない**
- LINE: `lin.ee/7qGC2YD` のみ記載可

### 6-4. ジョブ書き込み先（環境別自動切替）
- 開発環境：`book_maker_app/jobs/`
- exe 実行時：`exe と同階層/BookMaker_jobs/`
- Vercel/Lambda：`/tmp/book_maker/`
- 環境変数 `BOOK_MAKER_HOME` で上書き可

### 6-5. 禁止事項
- API キーをコード／設定ファイル／commit に含めない（フォーム入力のみ）
- ジョブ書き込み先を `_resource.writable_root()` 経由なしで直接決め打ちしない
- 旧 `POST /generate` を復活させない（廃止済み）
- prompts/ のテンプレを書き換えるときは voice.md v7.1 規約必須
- v6 教科書帯（H1=10/H2=58/H3=34/45,000字）の凍結ファイルは触らない

---

## 7. 既知の落とし穴

| 落とし穴 | 対策 |
|---------|------|
| Vercel の60秒タイムアウト | 本書全体生成（5〜10分）はローカル必須。タイトル10選までなら Web で完走 |
| Vercel のファイルシステムは `/tmp` のみ書込可 | `_resource.is_serverless()` で自動フォールバック |
| Vercel リクエストボディ4.5MB上限 | 大量ファイル送信は exe 経由が無難 |
| `google.generativeai` deprecated 警告 | 動作には影響なし。将来 `google-genai` 移行予定 |
| Windows Defender 警告（exe 起動時） | コード署名なしのため。ユーザーには「詳細情報→実行」と案内 |
| Pandoc reference_v7.docx 不在時 | `convert_to_docx()` でファイル存在チェック。なければ標準テンプレで動作 |
| 既存ジョブ履歴が localStorage に残る | キー名 `book_maker_projects_v3` を変えない限り互換維持 |
| ブラウザリロードで job_id 消失 | サーバー側 JOB_STATE は保持。クライアント側は localStorage `last_job_id` で復元可 |

---

## 8. Claude Code での再開コマンド例

```
@C:\Users\naoya\myproject\book_maker_app\_handoff_claude_code.md
を全文読み込んでください。

その上で、以下のいずれかを依頼します：
A. 機能追加：xxx を追加してほしい
B. バグ修正：xxx が動かないので調査してほしい
C. リリース：v1.0.2 として ... を追加してリリースしてほしい
D. 文書化：README をブラッシュアップしてほしい
E. 別書籍プロジェクトとの連携：cover-app-business の v7 サンプルを追加してほしい
```

### よく使う @記法参照
```
@app.py                            FastAPI エントリ
@generator.py                      書籍生成コア
@_resource.py                      環境別パス解決
@launcher.py                       デスクトップ起動
@prompts/system.txt                voice.md v7.1 規範
@prompts/structure.txt             v7 構造プロンプト（H1=4-5・H2=2-3）
@templates/index.html              メイン UI
@static/app.js                     画面制御
@README.md                         使い方
@C:\Users\naoya\myproject\Obsidian link\my-engine\v8\x-posts\drafts\voice.md
```

---

## 9. 残タスク・推奨ロードマップ

### 短期（次セッションで実行可能・1〜2時間）
- [ ] **Mac.app 版を追加**（Mac 環境で `./build.sh` → BookMaker.app → v1.0.x にアップロード）
- [ ] **README にバッジ追加**（`![Release](https://img.shields.io/github/v/release/harry-n2/book-maker-app)`）
- [ ] **README にスクリーンショット埋込**（起動／タイトル選択／完成画面）
- [ ] **コンソール窓を非表示化**（`console=False`・要トラブル時切り戻し検討）

### 中期（半日〜1日）
- [ ] **インストーラー化**（Inno Setup `BookMakerSetup.exe`・スタートメニュー登録）
- [ ] **`google.generativeai` → `google-genai` 移行**（deprecated 解消）
- [ ] **多端末同期**（プロジェクト履歴を Supabase / Firebase で同期）

### 長期（複数日）
- [ ] **コード署名**（年¥30,000・SmartScreen 警告解消）
- [ ] **Render 並行デプロイ**（Vercel 60秒制限を回避し Web で完走可能に）
- [ ] **挿絵対応**（画像生成→docx 埋込・別エンドポイント）

---

## 10. 関連プロジェクト（外部参照）

### 10-1. cover-app-business（v6/v7 ベンチマーク基準書）
```
C:\Users\naoya\myproject\Obsidian link\kindle project\cover-app-business\
├── 01_design/book_style_standard.md  v6/v7 併存基準書
├── 01_design/book_spec.md            文字数ガイドライン v3
├── 02_skills/book_writer.md          書籍ライター v3
└── 04_output/kindle publish/         v6 凍結書籍（『AI×フォルダ 収益化の教科書』）
```
※ 当プロジェクト（book_maker_app）は v7 基準で動作。cover-app-business の v6 凍結ファイルは触らない。

### 10-2. my-engine（口調規範）
```
C:\Users\naoya\myproject\Obsidian link\my-engine\
└── v8/x-posts/drafts/voice.md        v7.1 口調規範（必読）
```

---

## 11. ハリーへの最初の確認事項

Claude Code 再起動後、ハリーから新しい指示を受けた場合：

1. **「v1.0.2 を作りたい」** → Section 5-2 の手順
2. **「機能を追加したい」** → 該当ファイルを @記法で読込→修正→commit
3. **「バグが起きた」** → ローカル `python launcher.py` で再現＋ログ確認
4. **「ユーザーから問い合わせ」** → README のトラブルシューティング章を参照
5. **「Mac版がほしい」** → Mac マシンで `./build.sh` 案内

該当しない指示の場合、本ファイルの Section 9（残タスク）から優先度判定して提案してください。

---

最終確認：このファイルを全文読み込んだ時点で、Claude Code は本プロジェクトの全コンテキストを保持できているはずです。
