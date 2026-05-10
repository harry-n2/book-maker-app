# 引き継ぎ書：Google Antigravity（Book Maker App プロジェクト）

このファイル一つだけで、再起動後にプロジェクトを再開できるよう設計しています。
Antigravity を起動した直後にこのファイル全文を読み込ませてください。

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
著者：ハリー
LINE：lin.ee/7qGC2YD
```

---

## 1. プロジェクト概要

### 目的
ユーザー（AIリテラシー低い読者層）が4〜5ステップ入力するだけで Kindle KDP 入稿可能な電子書籍を自動生成するアプリ。

### 配布形態（3 種）
| 形態 | URL／場所 | 用途 |
|------|---------|------|
| デスクトップ exe | `dist/BookMaker.exe`（87.7MB） | エンドユーザー配布 |
| Web 版（Vercel） | https://bookmakerapp.vercel.app | インストール不要 |
| ローカル Python | `python launcher.py` | 開発用 |

### 技術スタック
- FastAPI + Uvicorn
- Google Gemini API（gemini-2.0-flash-exp）
- pypandoc-binary / python-docx / pypdf / trafilatura / Pillow
- PyInstaller

---

## 2. Antigravity 向け Subagent タスク分解

Antigravity の Subagent 機能を使って、以下の単位で並列タスクを実行できます。

### Subagent A：機能改修
- [ ] フォーム項目の追加・削除
- [ ] 進捗バー UI のブラッシュアップ
- [ ] エラーメッセージの日本語化チェック
- [ ] CSS のレスポンシブ対応強化

### Subagent B：プロンプト最適化
- [ ] `prompts/titles.txt` のフック型を10種から増やす
- [ ] `prompts/structure.txt` の検証ルール強化
- [ ] `prompts/promotion.txt` のクーポン文言バリエーション
- [ ] `prompts/description.txt` の5ブロック構成見直し
- ※ 編集時は voice.md v7.1 規範必読

### Subagent C：リリース管理
- [ ] CHANGELOG.md 自動生成（git log から）
- [ ] GitHub Releases バッジ追加（README）
- [ ] Mac.app 版追加（要 Mac 環境）
- [ ] スクリーンショット撮影＆README 埋込

### Subagent D：監査・QA
- [ ] 生成書籍の自動 lint（マークダウン強調記号 0件・命令形 0件 検証）
- [ ] structure.json の H1=4-5 / H2=2-3 / H3 章合計 0-2 検証
- [ ] Vercel デプロイ後の HTTP 200 自動チェック
- [ ] BookMaker.exe 起動時の所要時間測定

### Subagent E：ドキュメンテーション
- [ ] README の英訳版作成
- [ ] 動画チュートリアル用スクリプト作成
- [ ] FAQ ファイル新設

---

## 3. ファイル構成（参照用フルパス一覧）

### コアコード（編集対象）
```
C:\Users\naoya\myproject\book_maker_app\app.py                FastAPI エンドポイント
C:\Users\naoya\myproject\book_maker_app\generator.py          書籍生成コア
C:\Users\naoya\myproject\book_maker_app\references.py         参照素材取込
C:\Users\naoya\myproject\book_maker_app\_resource.py          環境別パス解決
C:\Users\naoya\myproject\book_maker_app\launcher.py           exe 起動エントリ
C:\Users\naoya\myproject\book_maker_app\BookMaker.spec        PyInstaller 設定
```

### プロンプト（編集時 voice.md v7.1 必読）
```
C:\Users\naoya\myproject\book_maker_app\prompts\system.txt
C:\Users\naoya\myproject\book_maker_app\prompts\titles.txt
C:\Users\naoya\myproject\book_maker_app\prompts\structure.txt
C:\Users\naoya\myproject\book_maker_app\prompts\chapter.txt
C:\Users\naoya\myproject\book_maker_app\prompts\reference.txt
C:\Users\naoya\myproject\book_maker_app\prompts\promotion.txt
C:\Users\naoya\myproject\book_maker_app\prompts\description.txt
```

### UI（フロントエンド）
```
C:\Users\naoya\myproject\book_maker_app\templates\index.html
C:\Users\naoya\myproject\book_maker_app\templates\reference_v7.docx
C:\Users\naoya\myproject\book_maker_app\static\style.css
C:\Users\naoya\myproject\book_maker_app\static\app.js
```

### 補助スクリプト
```
C:\Users\naoya\myproject\book_maker_app\make_icon.py          BookMaker.ico 再生成
C:\Users\naoya\myproject\book_maker_app\make_reference_doc.py Pandoc reference-doc 再生成
C:\Users\naoya\myproject\book_maker_app\build.bat             Windows exe ビルド
C:\Users\naoya\myproject\book_maker_app\build.sh              Mac/Linux exe ビルド
```

### 関連プロジェクト（外部参照）
```
C:\Users\naoya\myproject\Obsidian link\kindle project\cover-app-business\
  ├ 01_design\book_style_standard.md   v6/v7 併存基準書
  ├ 01_design\book_spec.md             v3 文字数ガイド
  └ 02_skills\book_writer.md           v3 ライター

C:\Users\naoya\myproject\Obsidian link\my-engine\
  └ v8\x-posts\drafts\voice.md         v7.1 口調規範（必読）
```

---

## 4. v7 仕様（書籍生成基準）

### 章立て（厳守・違反は再生成対象）
- H1：本編 4〜5章
- H2：各章 2〜3節
- H3：各章合計 0〜2 個（任意配置）
- 章末ブロックは H2 にカウントせず独立扱い

### 連結順
```
表紙（H1+H2+著者名）
→ 目次（Pandoc 自動）
→ はじめに → 本編 第1〜N章 → おわりに → 宣伝
（Kindle紹介文は連結対象外・別ファイル）
```

### 文字数
- 本文 8,000〜15,000字 ＋ コピペブロック 4,000〜7,500字
- 合計 15,000〜22,500字（KDP ¥250〜¥500 / KU 帯）

---

## 5. 口調規範（voice.md v7.1）

### 必読
```
@C:\Users\naoya\myproject\Obsidian link\my-engine\v8\x-posts\drafts\voice.md
```

### 厳守項目
- 地の文：丁寧調100%
- Scope A（著者述懐）：言い切り型OK
- Scope B（読者語りかけ）：丁寧語り掛け一択
- 命令形「〜しろ／〜してくれ」絶対禁止
- 「いかがでしたでしょうか」「皆さん、こんにちは」絶対禁止
- マークダウン強調記号「\*\*xxx\*\*」絶対禁止
- 中流階級KW（年収／時間単価／組織／年商／キャリア／45歳の壁）各章最低1回
- 失敗談バンクA〜G を各章1つ（章間重複なし）
- 冒頭1行は voice.md の10型から選択

### 著者プロフィール
- 「ハリー」名義のみ
- X アカウント名（@…）を本文・著者プロフに記載しない
- LINE: `lin.ee/7qGC2YD` のみ

---

## 6. Antigravity 用ガードレール（暴走防止）

### 絶対禁止
- API キーをコード／設定ファイル／commit に含めない
- 旧 `POST /generate` を復活させない（廃止済み・/generate-titles と /confirm-title/{job_id} を使う）
- voice.md v7.1 規約違反のテンプレ修正
- v6 教科書帯（cover-app-business 配下）の凍結ファイル改変
- ジョブ書込先を `_resource.writable_root()` 経由なしで決め打ち
- マークダウン強調記号「\*\*xxx\*\*」を新規追加
- X アカウント名を本文・プロフに記載

### 違反検知時のロールバック
- マークダウン強調 `**` が新規に入った → 当該ファイルを差分修正
- 命令形「〜しろ」が地の文に入った → 直接編集で除去
- voice.md 違反のプロンプト変更 → git revert

### 各 Subagent の終了条件
- Subagent A〜E は実行後に `python launcher.py` で起動確認 → curl で `/` 200 OK 確認
- 構造変更時は `_validate_structure()` 検証通過必須
- すべての出力前に「\*\* が0件か」grep audit

---

## 7. 完成済み機能リスト（v1.0.1 時点）

### 5ステップ UI（フォーム）
1. テーマ入力
2. 読者層選択（5択）
3. 著者名入力
4. 参照素材（URL・ファイル10個・画像10個・NotebookLM）
5. Gemini API キー（ユーザー入力・サーバー保存なし）

### 2段階UX
- POST /generate-titles → タイトル候補10選を生成
- 10カードラジオ → 1つ選択
- POST /confirm-title/{job_id} → 本編生成バックグラウンド開始

### 出力 5ファイル
- book_full.md（Markdown）
- book_full.docx（Word・KDP入稿可・reference_v7.docx 適用）
- title_candidates.md（10候補）
- book_description.md（KDP紹介文 720字）
- book_for_notebooklm.md（NotebookLM 取込用）

### デスクトップアプリ
- launcher.py：未使用ポート自動探索＋ブラウザ自動起動
- BookMaker.exe：87.7MB・アイコン埋込済み
- _resource.py：PyInstaller / Vercel / 開発 全環境対応

---

## 8. 既知の落とし穴（実証済み）

| 落とし穴 | 検知 | 対策 |
|---------|------|------|
| Vercel 60秒制限 | /confirm-title で504 | ローカル運用必須 |
| Vercel 読取専用 | 起動時500 | `_resource.is_serverless()` で /tmp |
| Vercel ボディ4.5MB上限 | 21ファイルで500 | exe 経由推奨 |
| `google.generativeai` deprecated | FutureWarning | 動作影響なし |
| Windows Defender 警告 | exe 初回起動 | 「詳細情報→実行」案内 |
| Pandoc reference 不在 | DOCX崩れ | `convert_to_docx()` 存在チェック |
| ブラウザリロードで job_id 消失 | UI リセット | サーバー JOB_STATE 保持・localStorage 復元 |

---

## 9. Antigravity 再起動コマンド例

### 起動直後

```
@C:\Users\naoya\myproject\book_maker_app\_handoff_antigravity.md
を全文読み込んでください。

その上で、以下の Subagent タスクのいずれかを起動：
- Subagent A：機能改修（UI／API）
- Subagent B：プロンプト最適化（要 voice.md v7.1 必読）
- Subagent C：リリース管理（v1.0.2 等）
- Subagent D：監査・QA
- Subagent E：ドキュメンテーション
```

### 並列実行例

```
以下の3つの Subagent を並列で起動してください：

Subagent 1：app.py の `/generate-titles` レスポンスタイムを計測する負荷テストスクリプトを作成
Subagent 2：generator.py の `_validate_structure()` にユニットテストを追加（H1=4-5・H2=2-3・H3 合計0-2）
Subagent 3：README にスクリーンショット用画像のディレクトリ docs/screenshots/ を新設し、撮影依頼テンプレを書く
```

---

## 10. Git / リリース 操作

### 現状確認
```bash
cd C:/Users/naoya/myproject/book_maker_app
git pull
git log --oneline -10
git tag -l
gh release list
```

### v1.0.2 リリース手順
```bash
# 変更を commit & push
git add -A
git commit -m "feat: ..."
git push

# tag 作成
git tag -a v1.0.2 -m "v1.0.2: ..."
git push origin v1.0.2

# exe 再ビルド
build.bat

# Releases 公開
gh release create v1.0.2 --title "..." --notes-file CHANGELOG.md --latest
gh release upload v1.0.2 dist/BookMaker.exe
```

---

## 11. 完成済み成果物の URL 一覧

| 種別 | URL |
|------|-----|
| GitHub | https://github.com/harry-n2/book-maker-app |
| Releases（最新） | https://github.com/harry-n2/book-maker-app/releases/latest |
| BookMaker.exe DL | https://github.com/harry-n2/book-maker-app/releases/download/v1.0.1/BookMaker.exe |
| Vercel 本番 | https://bookmakerapp.vercel.app |
| Vercel Inspect | https://vercel.com/harry-n2/book_maker_app |

---

## 12. ハリーへの最初の確認事項（Antigravity 経由）

Antigravity 再起動後、ハリーから新しい指示を受けた場合：

1. **「機能を追加したい」** → Subagent A
2. **「プロンプトを変えたい」** → Subagent B（voice.md v7.1 必読）
3. **「v1.0.2 を作りたい」** → Subagent C
4. **「QAしてほしい」** → Subagent D
5. **「ドキュメントを増やしたい」** → Subagent E

該当しない場合、本ファイル Section 9（残タスク）から優先度判定して提案してください。

---

最終確認：このファイルを全文読み込んだ時点で、Antigravity は本プロジェクトの全コンテキストを保持できているはずです。
