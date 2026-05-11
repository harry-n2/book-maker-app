# Handover for Codex / Antigravity

## Source
- Log file: `c:\Users\naoya\.cursor\projects\c-Users-naoya-myproject-Obsidian-link-kindle-project\terminals\2.txt`
- Relevant range: `1015-1026`
- Limit message: `You've hit your limit · resets May 16, 5pm (Etc/GMT-9)`

---

## Codex向け（簡潔・実行優先）

### 現状
- 利用上限到達中。再開は `May 16, 5pm (Etc/GMT-9)` 以降、または `/extra-usage` 申請。
- タスク進捗: `20 tasks (9 done, 2 in progress, 9 open)`
- 主な未完:
  - `v1.2.0 ローカル動作確認（ハリー依頼）`
  - `v2.0.0：プロンプト 7 本を汎用化＋無理配置撤廃`
  - `v1.2.0 commit & push（Vercel 自動デプロイ）`
  - `exe v1.2.0 ビルドと GitHub Release`
  - `v2.0.0 commit & push（Vercel 自動デプロイ）`

### 実行手順（CLI）
```powershell
# 1) リポジトリへ移動
cd "C:\Users\naoya\myproject\book_maker_app"

# 2) 差分とブランチ状態確認
git status
git branch --show-current
git log --oneline -n 10

# 3) v1.2.0 ローカル確認
# start.bat が起動スクリプト前提
.\start.bat

# 4) v1.2.0 commit & push（変更確認後）
git add -A
git commit -m "chore(v1.2.0): finalize local verification updates"
git push

# 5) exe ビルド（プロジェクト既定コマンドに合わせて実行）
# 例: npm run build:exe
# 例: pnpm build:exe

# 6) GitHub Release（gh CLI利用時の例）
# gh release create v1.2.0 <artifact_path> --title "v1.2.0" --notes "v1.2.0 release"

# 7) v2.0.0 変更を反映して commit & push
git add -A
git commit -m "feat(v2.0.0): generalize seven prompts and remove forced placements"
git push
```

### チェックポイント
- 上限到達直後の再開なので、作業漏れ確認を最優先に実施。
- Vercel 自動デプロイの成否を push 後に必ず確認。
- `v1.2.0` と `v2.0.0` の commit は混在させない。

---

## Antigravity向け（検証重視・手順明確）

### 目的
- 上限到達で中断したリリース作業を安全に再開し、`v1.2.0` と `v2.0.0` を順序通り完了する。

### 前提確認
```powershell
cd "C:\Users\naoya\myproject\book_maker_app"
git status
git remote -v
git branch --show-current
```

### フェーズA: v1.2.0 クローズ
```powershell
# A-1) ローカル起動確認
.\start.bat

# A-2) 必要ならテスト/ビルド確認（プロジェクト定義に合わせる）
# npm test
# npm run build

# A-3) コミットとプッシュ
git add -A
git commit -m "release(v1.2.0): validate locally and prepare deployment"
git push
```

### フェーズB: v1.2.0 exe + Release
```powershell
# B-1) exe ビルド（実際のスクリプト名を利用）
# npm run build:exe
# または pnpm build:exe

# B-2) GitHub Release（gh 利用例）
# gh release create v1.2.0 <artifact_path> --title "v1.2.0" --notes-file CHANGELOG.md
```

### フェーズC: v2.0.0 クローズ
```powershell
# C-1) 変更確認
git status
git diff

# C-2) コミットとプッシュ
git add -A
git commit -m "feat(v2.0.0): normalize 7 prompts and remove unnatural placements"
git push
```

### リスク管理
- 上限復帰直後は stale 状態が出やすいので、`git pull --rebase` 要否を事前確認。
- 同一ブランチで複数リリース作業が混線しないよう、フェーズ単位で完了判定する。
- 追加利用が必要な場合は `/extra-usage` を admin に申請。

