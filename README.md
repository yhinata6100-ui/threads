# Threads 自動投稿システム（Windowsローカル版）

Notion を投稿の予約台帳にして、**あなたのWindows PC上**でThreads APIを定期的に叩いて自動投稿する仕組みです。
クラウド（GitHub Actions）は使わず、Pythonスクリプト＋Windowsタスクスケジューラだけで完結します。
PCの電源が入っていてWindowsにログインしている時間帯のみ動作します。

## できること

- Notionの投稿管理DBに「投稿文＋投稿日時」を入れておくと、時刻が来たらタスクスケジューラが自動でThreadsに投稿（スレッド形式の連結投稿にも対応）
- 投稿後のインプレッション・いいね・コメント等をThreadsから取得してNotionに自動反映
- 投稿実績を `docs/kpi_data.json` に書き出し、ローカルの簡易ダッシュボードで確認
- Threadsの長期アクセストークンを月2回自動リフレッシュ

## APIキーの入力場所

**`windows\setup.bat` を実行すると聞かれる質問に答えるだけで、キーがこのPCの `.env` に保存されます。**
`.env` は `.gitignore` 済みなのでGitにはコミットされず、他人に見られることもありません。
コードやリポジトリに直接キーを書き込むことはしていません（漏えいのリスクを避けるため）。

## セットアップ手順

### 0. 前提
- Windows 10 / 11
- [Python](https://www.python.org/downloads/) がインストール済み（インストール時に **"Add python.exe to PATH"** に必ずチェック）
- このリポジトリをPC上にダウンロード or `git clone` 済み

### 1. Meta開発者アプリでThreadsのアクセストークンを発行
1. [Meta for Developers](https://developers.facebook.com/) で開発者アプリを作成し、Threads APIを追加
2. `threads_basic` / `threads_content_publish` / `threads_manage_insights` の権限で短期トークンを発行
3. `https://graph.threads.net/access_token?grant_type=th_exchange_token&client_secret=<APP_SECRET>&access_token=<短期トークン>` で長期トークン（60日）に交換

### 2. Notionインテグレーションを準備
1. [Notion Integrations](https://www.notion.so/my-integrations) でインテグレーションを作成し、シークレットキーを取得
2. 投稿DBを作りたい親ページを、そのインテグレーションに「接続」

### 3. APIキーを入力
エクスプローラーで `windows\setup.bat` をダブルクリック（または `cmd` で実行）。
依存パッケージのインストール後、以下を順番に聞かれるので入力する。

- Notionのシークレットキー
- Notionの親ページID（URLのままでも可）
- 投稿管理DB / リサーチDBのID → **この時点ではまだ無いので空Enterで飛ばしてOK**
- Threadsの長期アクセストークン

### 4. NotionのDBを作成
```
windows\run_setup_notion.bat
```
実行すると `NOTION_DATABASE_ID` / `NOTION_RESEARCH_DB_ID` が表示されるので、
もう一度 `windows\setup.bat` を実行してその2つを入力する。

### 5. 疎通確認
```
windows\run_post_scheduled.bat
```
エラーなく「投稿予定なし」と出れば接続成功。Notionに投稿を1件入れてから再実行すると投稿されるか確認できる。

### 6. 定期実行を登録
PowerShellを **「管理者として実行」** で開き、

```powershell
cd <このリポジトリのフォルダ>
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\windows\register_tasks.ps1
```

タスクスケジューラ（`taskschd.msc`）に以下の4つが登録される。

| タスク名 | 頻度 |
|---|---|
| Threads-PostScheduled | 8:00〜23:55、10分おき |
| Threads-SyncMetrics | 8:00〜23:30、30分おき |
| Threads-ExportKpi | 毎日23:30（保険の全体書き出し） |
| Threads-RefreshToken | 毎月1日・15日 9:00 |

削除したい場合は同様に管理者PowerShellで `.\windows\unregister_tasks.ps1` を実行する。

### 7. ダッシュボードを見る
```
windows\run_dashboard.bat
```
ブラウザで `http://localhost:8765/` が開き、投稿実績を確認できる。

## 投稿の入れ方

Notionの投稿管理DBに、以下の列で1行追加すると予約完了です。

- `投稿文`：本文。複数投稿を1本のスレッド（返信チェーン）として連結したい場合は、単独行の `---` で区切る
- `投稿日`：**必ず時刻付き**（例 `2026-08-01T21:14:00+09:00`）。日付だけだと投稿されません
- `投稿済み`：チェックボックス（未投稿は空のまま）

## 運用ルール（元キットの安全ノウハウを踏襲）

- 投稿上限は1日10件（事故防止の安全装置、`src/post_scheduled.py` の `DAILY_POST_LIMIT`）
- 「稼ぐ／副業／稼げる」等の金銭ワードはThreadsに表示抑制されるため避ける
- 金額に「円」を付けない（例：30万達成）
- 初めてライブ投稿を試すときは、投稿件数を絞って本人確認をしてから本運用に入る
- PCがスリープ／シャットダウンしている間は動作しない（電源設定で自動スリープをオフにするか、稼働時間中は起こしておく）

## ディレクトリ構成

```
src/                 自動化スクリプト本体
  main.py              Notion / Threads API 共通関数
  post_scheduled.py    予約投稿の実行
  sync_metrics.py      メトリクス同期
  export_kpi.py        ダッシュボード用JSON書き出し
  refresh_token.py     トークンリフレッシュ（.envを直接更新）
  setup_notion.py      NotionDB初期作成（手動・初回のみ）
  kpi_input.py          手入力KPI（オプチャ数・アポ数）の記録CLI
windows/             Windows用セットアップ・起動・タスク登録スクリプト
  setup.bat / setup_env.py   APIキーの対話入力
  run_*.bat                  各スクリプトの起動用バッチ
  register_tasks.ps1         タスクスケジューラへの登録
  unregister_tasks.ps1       登録解除
docs/                ローカルダッシュボード（index.html + kpi_data.json）
content-kit/         投稿の型・NGルールを書き込むための空テンプレート
```
