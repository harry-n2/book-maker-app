# BookJobSpec v1 ― 電子書籍生成の中核JSON契約（仕様のみ・コード実装なし）

> 作成: 2026-06-20 ／ 状態: **仕様ドラフト（オーナー承認待ち）** ／ スコープ: 電子書籍(テキスト)のみ（マンガ・表紙・画像は対象外）
> 目的: 「1冊の本＝1つの再実行可能な仕様」を固定し、企画→タイトル→章立て→本文→紹介文→出力の全工程を、同じ入力なら同じ品質で再現でき、途中失敗から再開できるようにする。
> 根拠: 既存コード監査＋fusion合議（Codex全成功）。Geminiモデル状況は **Google公式docで一次確認済（2026-06-20）**。
> 本ファイルは契約の定義（仕様）。実装・DBマイグレーション・デプロイはオーナーの個別指示まで行わない。

---

## 0. 設計原則（なぜこの契約が要るか）
1. **AIに自由裁量を残すほど品質が揺れる** → 各工程の入出力をJSONで固定し、検証可能にする。
2. **正本は「章ごとMarkdown＋構造化メタ」**。Word(docx)/紹介文/NotebookLM用は**いつでも作り直せる派生物**（正本にしない）。
3. **冪等**：同じジョブキーは再生成せず保存済みを返す。
4. **反捏造を保持**：全主張に出所ラベル。素材外の実績・数字は使わない（既存アプリの強みを契約化）。

---

## 1. トップレベル: BookJob

```json
{
  "job_id": "bk_20260620_3f9a",
  "schema_version": "book_job_spec_v1",
  "workflow_version": "wf_v1",
  "status": "running",
  "input_hash": "sha256(正規化入力)",
  "created_at": "ISO8601",
  "updated_at": "ISO8601",
  "model_policy_id": "mp_v1",
  "user_inputs": { "...": "§3" },
  "artifacts": {
    "planning_brief": "ref:step:planning",
    "title_package": "ref:step:title",
    "structure": "ref:step:structure",
    "chapters": ["ref:chapter:00_intro", "ref:chapter:01", "..."],
    "front_back_matter": "ref:step:matter",
    "sales_copy": "ref:step:sales",
    "exports": { "md": "blob://...", "docx": "blob://...", "notebooklm": "blob://..." }
  },
  "evidence_ledger_id": "ev_...",
  "current_step": "chapter_write",
  "error": null
}
```

## 2. 工程（Step）と状態機械

工程順（HITL=人の承認ゲート付き）:
```
intake(素材取込)  →  planning(企画) [承認A]  →  title(タイトル/販売文) [承認B]
 →  structure(章立て) [承認C]  →  chapter_write(本文・章ごと)  →  matter(はじめに/おわりに/奥付)
 →  sales(Kindle紹介文)  →  qa(品質評価)  →  export(md/docx/紹介文/NotebookLM)
```
- 各Stepの `status` ∈ `pending | running | needs_review | approved | failed | cached`。
- HITLは **planning / title / structure** の3つに承認ゲートを置く（fusion合議：人手は要所のみ）。本文は章単位で「失敗章だけ再生成」。

### Step共通レコード（book_steps）
```json
{
  "job_id": "bk_...",
  "step_name": "structure",
  "status": "approved",
  "input_json": { "...": "..." },
  "output_json": { "...": "..." },
  "input_hash": "sha256(...)",
  "idempotency_key": "bk_..|structure|<input_hash>|<prompt_version>",
  "prompt_version": "structure_v1",
  "model_id": "gemini-3.5-flash",
  "generation_config": { "temperature": 0.3, "topP": 0.9, "seed": 12345 },
  "attempt_count": 1,
  "error": null,
  "completed_at": "ISO8601"
}
```
**冪等キー** = `job_id + step_name + input_hash + prompt_version`。完了済キーは再生成せず返す。入力/プロンプトが変われば別キー。

## 3. user_inputs（intake）
```json
{
  "theme": "テーマ1行",
  "target_reader": "選択 or 自由（企画で精緻化）",
  "author": "表示著者名",
  "profile": {
    "name": "", "author_bio": "", "tone": "",
    "target_keywords": [], "failure_bank": [], "voice_types": []
  },
  "references": [
    {"ref_id":"r1","kind":"url|file|pasted|notebooklm","label":"","status":"ok|partial|failed|oversize","char_count":0,"excerpt":"","exclude_reason":null}
  ],
  "publish_format": "kindle_ebook",
  "mode": "omakase | guided | advanced"
}
```
- intakeで**素材マニフェスト**を作り、取得失敗/薄い素材を承認前に警告（fusion R9）。

## 4. planning_brief（企画部長フェーズ・承認A）
```json
{
  "target_reader": "誰の・どの悩み",
  "deep_need": "本音の欲求",
  "core_angles": ["切り口1","切り口2","切り口3"],
  "recommended_angle": "1案",
  "promise": "読後に得る変化",
  "differentiation": "競合との違い（競合情報が無ければ『仮説』と明示）",
  "evidence_policy": "使ってよい/禁止の根拠範囲",
  "kindle_category_hypothesis": "想定カテゴリ・検索語",
  "constraints_for_next_steps": "タイトル/章立て/本文へ渡す制約文"
}
```
- 初心者は必須入力3つ（何の本/誰に/語れる経験）→AIが切り口3案→選ぶだけ。詳細は「高度な設定」に隠す。

## 5. title_package（編集者＋頭脳・承認B）
```json
{
  "fact_ledger": {"allowed_claims":[], "forbidden_claims":[], "keywords":[]},
  "candidates": [
    {"rank":1,"type":"悩み直撃|読者明示|変化到達|逆張り|ノウハウ明示",
     "title":"主タイトル","subtitle":"サブ",
     "scores":{"searchability":0,"benefit":0,"kindleness":0,"hype_risk":0,"content_match":0},
     "note":"推奨/安全だが弱い/攻めだが要注意"}
  ],
  "selected_index": 0
}
```
- PASONAは**配置フレームのみ**（主張は fact_ledger からのみ引用）。誇大・成果保証・未確認数字は禁止。

## 6. structure（章立て・承認C）
```json
{
  "title": "", "subtitle": "",
  "intro": {"id":"00_intro","key_message":"","sections":[]},
  "chapters": [
    {"id":"01","title":"第1章 …","role":"","reader_change":"","key_message":"",
     "evidence_refs":["r1"],"avoid":[],"voice_type":"","failure_bank":"",
     "sections":[{"h2":"","summary":"","subsections":[]}]}
  ],
  "outro": {"id":"99_outro","key_message":"","sections":[]}
}
```
- 4〜5章、各章2〜3 sections（既存規律を継承）。各章に役割/読者変化/根拠素材/避ける内容（fusion R6）。

## 7. chapter（本文・製造ライン・章ごと冪等）
各章は1発生成しない。`章ブリーフ → 小節 → ブロック生成 → 反捏造検証 → 密度検証 → 増補 → 統合編集 → 章末アクション` （fusion R5）。
```json
{
  "job_id":"bk_...","chapter_id":"01","title":"",
  "brief": {"purpose":"","reader_pain":"","promise":"","claims":[],
            "evidence_refs":["r1"],"forbidden":[],"example_type":"","action":"","target_chars":4000},
  "blocks": [{"role":"導入","target_chars":400,"markdown":""}],
  "qa": {"claim_clear":true,"too_abstract":false,"examples_enough":true,"actionable":true,
         "no_fabrication":true,"no_repetition":true,"page_turner":true,"issues":[]},
  "markdown":"（統合後本文）","revision_no":1,"status":"approved",
  "style_bible_ref":"sb_...", "glossary_ref":"gl_..."
}
```
- **Style Bible / 用語集**を全章に注入し文体・固有名詞・語調を統一（fusion R7）。
- 反捏造検証は「診断のみ→次工程で修正」（自己採点同時修正は甘くなる）。

## 8. quality scores（品質評価エンジン・fusion R8）
```json
{"planning":0,"originality":0,"trust":0,"readability":0,"sales_power":0,
 "overall":0,"low_score_targets":["chapter:03 examples"],"threshold":70}
```
- 閾値未満の箇所**だけ**再生成。改善前後の差分を保存。

## 9. export & KDP適合（fusion R8/R10）
- 正本Markdown→docx生成時に **Word見出しスタイル(H1/H2/H3)・章頭改ページ・Interactive TOC・固定奥付テンプレ**を適用。
- 奥付固定: 書名/著者/発行日/Copyright/連絡先 or 発行者/版。
- 紹介文lint: 4000字以内・ランキング主張/誇大/内容不一致/商標誤用を検査。
- **AI生成コンテンツ申告メモ**を自動同梱（`ai_generated_text: yes`, `ai_assisted: ...`, `human_reviewed: yes`, 画像/翻訳: なし）。KDP出版画面での申告用（※KDP公式手順は実装時に再確認）。

## 10. Model Policy（fusion R7/R9・公式doc一次確認済 2026-06-20）
`gemini-2.0-flash` は **Shut down 済（使用不可）**。`latest`エイリアス禁止・`model_id`固定保存。
| ティア | 用途 | 推奨 model_id（Stable） |
|---|---|---|
| economy | 素材抽出/要約/整形/NotebookLM用 | `gemini-2.5-flash-lite` or `gemini-3.1-flash-lite` |
| standard | タイトル/章立て/本文ドラフト/紹介文初稿 | `gemini-2.5-flash` or `gemini-3.5-flash` |
| premium | 企画診断/編集レビュー/販売文磨き/最終QA | `gemini-2.5-pro` |
- 温度: 構造化工程 0.2–0.4 / 本文 0.6–0.8 / 校正 0.2–0.3。`seed`固定保存（完全同一は不保証→品質再現を評価セットで測定）。
- BYOK鍵はフロント露出禁止・サーバ一時利用・使用量上限/日次上限/削除機能。

## 11. 永続化（fusion R1/R2・テキストのみ＝軽量で足りる）
- `book_jobs` / `book_steps` / `book_chapters` を Postgres（Neon/Supabase/Vercel Postgres）に保存。Blobは原稿/派生物。
- 実行は**章ごとの短いAPI呼び出し**に分割（HITL型なのでユーザー操作で進む）。1章がVercel実行時間に近づく場合のみ QStash/Inngest/Trigger.dev 等の軽量キューを後付け（過剰インフラを避ける）。
- 再開: job_id→完了Stepはスキップ→未完了章だけ生成→全章完了でMarkdown結合→派生物生成。

## 12. 反捏造エビデンス台帳（fusion R3）
```json
{"evidence_id":"ev_...","items":[
  {"claim":"主張文","source":"素材由来|ユーザー確認|推論|禁止","ref_id":"r1","usable":true}
]}
```
- 本文/タイトル/紹介文の全主張をこの台帳に照合。`禁止`/`推論` を実績・数字として出さない。

---

## 13. 検証・回帰ゲート（毎ラウンド共通）
冪等 / 章再開 / Run Manifest差分 / 反捏造（未根拠数字ゼロ）/ KDP整形（見出し階層・目次・奥付）/ 紹介文lint / 文字数 / モデルID固定。P0/P1残存でリリースしない。

## 14. 要・一次確認（実装着手時）
- KDPのAI申告・メタデータ規約の最新手順、docx/TOC仕様。
- Gemini各モデルの単価・`seed`/`thinkingLevel`等の生成パラメータ（公式 generate-content doc）。
- Postgres/キューの採用先（Neon＋Vercel Blob を第一候補）。

## 15. 次の一手（実装ではない）
本BookJobSpec v1をオーナー承認 → 承認後 **ラウンド1（ジョブ基盤の永続化＋モデル更新）** から実装着手（ローカル全検証→合格後に1デプロイ）。
