# Threads 自動投稿システム

Notion を投稿の予約台帳にして、GitHub Actions が定期的に Threads API を叩いて自動投稿する仕組みです。
元は Mac + cron 前提のスターターキットでしたが、このリポジトリでは **GitHub Actions で完結する構成に作り直して**あります。

## できること

- Notionの投稿管理DBに「投稿文＋投稿日時」を入れておくと、時刻が来たら GitHub Actions が自動でThreadsに投稿（スレッド形式の連結投稿にも対応）
- 投稿後のインプレッション・いいね・コメント等をThreadsから取得してNotionに自動反映
- 投稿実績を `docs/kpi_data.json` に書き出し、GitHub Pages でダッシュボード表示
- Threadsの長期アクセストークンを月2回自動リフレッシュ（任意設定）

## 重要：APIキーはこのリポジトリに直接書き込みません

`.env` はローカル動作確認専用で `.gitignore` 済みです。GitHub Actions からは
**リポジトリの Secrets** を読みます。APIキーをコードやコミットに平文で入れると、
リポジトリを見られる人・Actionsログ経由で漏えいするリスクがあるため、必ず以下の手順で
`Settings > Secrets and variables > Actions` に登録してください（このセッションでは代理登録できません）。

| Secret名 | 内容 |
|---|---|
| `NOTION_API_KEY` | Notionインテグレーションのシークレットキー |
| `NOTION_DATABASE_ID` | 投稿管理DBのID（`setup_notion.py` 実行後に取得） |
| `NOTION_RESEARCH_DB_ID` | リサーチDBのID（同上、任意） |
| `THREADS_ACCESS_TOKEN` | Threadsの長期アクセストークン |
| `GH_ADMIN_TOKEN` | （任意）トークン自動リフレッシュを使う場合のみ。Secrets: Read/Write 権限のFine-grained PAT |

## セットアップ手順

### 1. Meta開発者アプリでThreadsのアクセストークンを発行
1. [Meta for Developers](https://developers.facebook.com/) で開発者アプリを作成し、Threads APIを追加
2. `threads_basic` / `threads_content_publish` / `threads_manage_insights` の権限で短期トークンを発行
3. `https://graph.threads.net/access_token?grant_type=th_exchange_token&client_secret=<APP_SECRET>&access_token=<短期トークン>` で長期トークン（60日）に交換
4. 得られたトークンを GitHub Secrets の `THREADS_ACCESS_TOKEN` に登録

### 2. Notionの準備
1. [Notion Integrations](https://www.notion.so/my-integrations) でインテグレーションを作成し、シークレットキーを取得
2. 投稿DBを作りたい親ページを、そのインテグレーションに「接続」
3. ローカルで `.env`（`.env.example` をコピー）に `NOTION_API_KEY` / `NOTION_PARENT_PAGE_ID` を設定し、以下を実行

```bash
pip install -r requirements.txt
python src/setup_notion.py
```

4. 出力された `NOTION_DATABASE_ID` / `NOTION_RESEARCH_DB_ID` を GitHub Secrets に登録

### 3. GitHub Pagesを有効化（ダッシュボード）
`Settings > Pages` で Source を `Deploy from a branch`、ブランチを `main` / フォルダを `/docs` に設定すると
`https://<user>.github.io/<repo>/` でダッシュボードが見られます。

### 4. 動作確認
Actions タブから各ワークフローを `Run workflow`（workflow_dispatch）で手動実行して確認できます。
初回は投稿を自動で走らせず、まず `python src/main.py` 相当の疎通確認（Notion接続）から。

## 投稿の入れ方

Notionの投稿管理DBに、以下の列で1行追加すると予約完了です。

- `投稿文`：本文。複数投稿を1本のスレッド（返信チェーン）として連結したい場合は、単独行の `---` で区切る
- `投稿日`：**必ず時刻付き**（例 `2026-08-01T21:14:00+09:00`）。日付だけだと投稿されません
- `投稿済み`：チェックボックス（未投稿は空のまま）

`src/main.py` の `save_posts()` を使えば、Notion APIやNotion MCP経由でもコードから投稿を積めます。

## 自動実行のスケジュール（GitHub Actions）

| ワークフロー | 頻度 |
|---|---|
| `post-scheduled.yml` | JST 8:00〜23:55、10分おき |
| `sync-metrics.yml` | JST 8:00〜23:30、30分おき |
| `export-kpi.yml` | JST 23:30（保険の全体書き出し） |
| `refresh-token.yml` | 毎月1日・15日 JST 9:00 |

GitHub Actionsのスケジュール実行は負荷状況により数分〜十数分遅延することがあります。厳密な時刻指定が必須の運用には向きません。

## 運用ルール（元キットの安全ノウハウを踏襲）

- 投稿上限は1日10件（事故防止の安全装置、`post_scheduled.py` の `DAILY_POST_LIMIT`）
- 「稼ぐ／副業／稼げる」等の金銭ワードはThreadsに表示抑制されるため避ける
- 金額に「円」を付けない（例：30万達成）
- 初めてライブ投稿を試すときは、投稿件数を絞って本人確認をしてから本運用に入る

## ディレクトリ構成

```
src/               自動化スクリプト本体
  main.py            Notion / Threads API 共通関数
  post_scheduled.py  予約投稿の実行（Actionsから定期実行）
  sync_metrics.py    メトリクス同期（Actionsから定期実行）
  export_kpi.py      ダッシュボード用JSON書き出し
  refresh_token.py   トークンリフレッシュ
  setup_notion.py    NotionDB初期作成（手動・初回のみ）
  kpi_input.py        手入力KPI（オプチャ数・アポ数）の記録CLI
docs/              GitHub Pagesダッシュボード（index.html + kpi_data.json）
content-kit/       投稿の型・NGルールを書き込むための空テンプレート
.github/workflows/ 自動実行の定義
```
