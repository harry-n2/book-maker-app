# Book Maker

テーマを書くだけで、Kindle KDP に入稿可能な電子書籍（Markdown ＋ Word）を自動生成する Web アプリです。AI リテラシーが低い方でも、4ステップのフォーム入力で完成します。

---

## 特長

- 質問は4つだけ（テーマ／読者層／著者名／APIキー）
- ベストセラー帯の構成（9章・本文＋3層コピペブロック・全見出し改ページ）を自動適用
- voice.md v7.1 規範（です・ます調／命令形禁止／中流階級KW／失敗談バンク）を遵守
- 出力は `book_full.md` ＋ `book_full.docx`（KDP 入稿可能形式）
- ローカル実行（書籍データは外部に送信されない／API キーはセッション内のみ保持）

---

## 起動方法

### 🎁 一番カンタン：BookMaker.exe（Windows 用デスクトップアプリ）

1. `dist/BookMaker.exe` をダブルクリックするだけ
2. 自動でブラウザが開きます（http://127.0.0.1:8765）
3. ジョブの保存先：`BookMaker.exe と同じフォルダ/BookMaker_jobs/`
4. 終了するにはコンソールウィンドウを閉じます

> exe が無い場合は、自分でビルド可能：`build.bat` をダブルクリック → `dist/BookMaker.exe` 完成（約3〜5分）

### Windows（Python 直接実行）

1. このフォルダを丸ごと配置（例：`C:\Users\naoya\myproject\book_maker_app\`）
2. `start.bat` をダブルクリック
3. 自動でライブラリがインストールされ、サーバーが起動します
4. ブラウザで [http://127.0.0.1:8765](http://127.0.0.1:8765) を開きます

### Mac / Linux / WSL

```bash
cd book_maker_app
chmod +x start.sh
./start.sh
```

ブラウザで [http://127.0.0.1:8765](http://127.0.0.1:8765) を開きます。

---

## 使い方（4ステップ）

1. **どんな本を作りますか？**
   テーマを 1〜2 行で書きます。具体的なほど良い本が出ます。

2. **読者は誰ですか？**
   5つの選択肢から1つを選びます（中堅幹部／専門職／経営者／副業層／フリーランス）。

3. **著者名（ペンネーム可）**
   書籍の著者として表示される名前です。

4. **Gemini API キー**
   [Google AI Studio](https://aistudio.google.com/app/apikey) で無料で取得できます。
   コピーして貼り付けてください。
   ※ キーはセッション内のメモリのみで保持され、サーバーには保存されません。

「本を作成する」を押すと、5〜10分で完成します。

---

## 出力ファイル

完成画面で以下の2ファイルがダウンロードできます。

| ファイル | 用途 |
|---------|------|
| `book_full.md` | Markdown 形式。でんでんコンバーター等で epub 化するときに使用 |
| `book_full.docx` | Word 形式。Kindle KDP に直接アップロード可能 |

---

## API キーの取得方法（Gemini）

1. [Google AI Studio](https://aistudio.google.com/app/apikey) にアクセス
2. Google アカウントでログイン
3. 「Create API key」をクリック
4. 生成された `AIzaSy...` で始まるキーをコピー
5. アプリのフォーム4番目に貼り付け

無料枠で本書1冊（約45,000字）を1〜2回生成できます。

---

## トラブルシューティング

| 症状 | 対処 |
|------|------|
| 「Incorrect API key」エラー | Gemini API キーが間違っています。Google AI Studio で再発行してください |
| 「ModuleNotFoundError」 | `python -m pip install --user -r requirements.txt` を手動実行 |
| 起動時に Python が見つからない | [Python 3.10 以上](https://www.python.org/downloads/) をインストール |
| ポート 8765 が使われている | `app.py` 末尾の `port=8765` を別の番号に変更 |
| 文字化け（Windows） | コマンドプロンプトを「コードページ 65001（UTF-8）」で開いてください |
| Word でレイアウト崩れ | 目次を右クリック→「フィールド更新」→「目次をすべて更新する」 |

---

## 仕組み（参考）

```
ユーザー入力（4項目）
    │
    ▼
[1] Gemini API で目次生成（タイトル＋9章のフック型・失敗談・核メッセージ）
    │
    ▼
[2] Gemini API で各章本文を順次生成（voice.md v7.1 規範のシステムプロンプト）
    │
    ▼
[3] Gemini API で各章末の3層コピペブロック生成（AI／PowerShell／Bash）
    │
    ▼
[4] 句点改行ルール適用（。で段落分割）
    │
    ▼
[5] 全見出し前に改ページ挿入
    │
    ▼
[6] Pandoc で MD → DOCX 変換（目次自動生成・改ページ反映）
    │
    ▼
ダウンロード提供
```

---

## ファイル構成

```
book_maker_app/
├── app.py                FastAPI サーバー
├── generator.py          書籍生成コアロジック
├── prompts/
│   ├── system.txt        共通システムプロンプト（voice.md v7.1 規範）
│   ├── outline.txt       目次生成プロンプト
│   ├── chapter.txt       章生成プロンプト
│   └── reference.txt     3層コピペブロック生成プロンプト
├── templates/
│   └── index.html        メインUI
├── static/
│   ├── style.css         スタイル
│   └── app.js            画面制御
├── jobs/                 生成書籍の保存先（job_id ディレクトリ）
├── requirements.txt      依存パッケージ
├── start.bat             Windows 起動スクリプト
├── start.sh              Mac/Linux 起動スクリプト
└── README.md             本ファイル
```

---

## 制限事項

- 1冊あたりの想定文字数：35,000〜50,000 字（Gemini の単発レスポンス上限内）
- 生成時間：5〜10 分（Gemini のレスポンス速度に依存）
- 挿絵：未対応（テキスト主体の教科書型）。後日手動追加または別アプリで対応してください
- 表紙画像：未対応。Canva 等で別途作成してください

---

## ライセンス

社内・個人利用は自由です。再配布や商用提供時は事前にご相談ください。
