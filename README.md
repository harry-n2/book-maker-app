# Book Maker

Book Maker は、テーマ・著者プロフィール・参考資料から、Kindle向けの原稿を生成するWebアプリです。

初めて使う方は、まず [FIRST_TIME_USER_MANUAL.md](./FIRST_TIME_USER_MANUAL.md) を読んでください。

## できること

- 参考資料を読み込んで本の材料にする
- タイトル候補を10個生成する
- 選んだタイトルから章立てを作る
- 章立てを確認・修正してから本文を生成する
- Markdown / Word / Kindle商品説明文を出力する
- 著者ごとに口調、背景、実績、読者像を調整する
- 出力本文から内部タグ、不要な記号、生成由来が分かる表記を自動で除去する

## 使うもの

- Gemini API キー
- 本のテーマ
- 著者名・著者プロフィール
- 参考資料
  - URL
  - PDF / Word / Markdown / Text / CSV
  - 画像
  - テキスト直接貼り付け

## Web版

https://bookmakerapp.vercel.app

## ローカル起動

Windows:

```powershell
cd C:\Users\naoya\myproject\book_maker_app
.\start.bat
```

Mac / Linux:

```bash
cd book_maker_app
chmod +x start.sh
./start.sh
```

起動後、ブラウザで `http://127.0.0.1:8765` を開きます。

## 基本の流れ

1. テーマ、読者、著者情報を入力する
2. 参考資料を入れる
3. Gemini APIキーを入力する
4. 参考資料の読み込み結果を確認する
5. タイトル候補から1つ選ぶ
6. 章立てを確認・必要なら修正する
7. 本文を生成する
8. Markdown / Word / 商品説明文をダウンロードする

## 出力ファイル

| ファイル | 内容 |
|---|---|
| `book_full.md` | 本文全文のMarkdown |
| `book_full.docx` | 本文全文のWord |
| `title_candidates.md` | タイトル候補一覧 |
| `book_description.md` | Kindle商品説明文 |
| `book_for_notebooklm.md` | NotebookLM確認用 |

## 注意点

- 生成結果は出版前に必ず確認してください。
- 著者プロフィールや参考資料にない実績・数字・事例は入力しない限り使わない設計です。
- 出力時に `*`、OpenXML改ページタグ、`第99章`、生成由来が分かる表記は除去されます。
- URL取得に失敗する場合は、テキスト直貼り欄に本文を貼るのが確実です。
- Vercel版では長時間生成や大容量ファイルで制限に当たる場合があります。その場合はローカル版を使ってください。

## 開発者向け

主要ファイル:

- `app.py`: FastAPIアプリ本体
- `generator.py`: 書籍生成ロジック
- `references.py`: 参考資料の取り込み
- `templates/index.html`: 画面
- `static/app.js`: フロントエンド処理
- `prompts/`: 生成プロンプト
- `api/index.py`: Vercel用エントリ

確認コマンド:

```powershell
python -m py_compile app.py generator.py references.py _resource.py pypandoc.py
node --check static\app.js
```
