# Monitoring MVP Backend

チーム向けサービス監視ツールの MVP バックエンドです。  
FastAPI を API サーバー、PostgreSQL を保存先、worker を定期監視プロセスとして分離し、ローカルで動かしやすい構成を優先しています。

現時点では、以下まで実装済みです。

- ユーザー登録 / ログイン / JWT 認証
- プロジェクト作成 / 一覧 / 詳細取得
- プロジェクトメンバー管理
- 監視対象サービスの登録 / 一覧 / 更新
- worker による定期監視
- `check_results` への履歴保存
- dashboard API の軽量取得
- retention による古い監視履歴の削除
- project 単位の通知チャネル設定
- Discord Webhook 通知

## 技術スタック

- Python
- FastAPI
- PostgreSQL
- SQLAlchemy 2.x
- Alembic
- JWT Bearer 認証
- Docker / docker-compose
- httpx

## アーキテクチャ

このプロジェクトは大きく 3 つの役割に分かれています。

- `api`
  ユーザー認証、project / service / notification channel 管理、dashboard API を提供します。
- `worker`
  1 分ごとに有効な service を監視し、`check_results` へ保存します。必要に応じて通知も送ります。
- `db`
  PostgreSQL。アプリケーションデータと監視履歴を保存します。

worker は API とは別プロセスで動き、将来 ECS / Fargate で別サービスとして分離しやすい構成にしています。

## ディレクトリ構成

```text
.
├─ alembic
│  ├─ env.py
│  ├─ script.py.mako
│  └─ versions
├─ app
│  ├─ api
│  │  ├─ deps.py
│  │  ├─ router.py
│  │  └─ routes
│  ├─ core
│  │  ├─ config.py
│  │  └─ security.py
│  ├─ db
│  │  ├─ base.py
│  │  └─ session.py
│  ├─ models
│  ├─ schemas
│  └─ main.py
├─ worker
│  ├─ Dockerfile
│  ├─ main.py
│  ├─ notifications.py
│  ├─ retention.py
│  └─ retention_job.py
├─ .env.example
├─ alembic.ini
├─ docker-compose.yml
├─ Dockerfile
├─ README.md
└─ requirements.txt
```

## 主なテーブル

- `users`
- `projects`
- `project_members`
- `services`
- `check_results`
- `service_notification_states`
- `project_notification_channels`

### 通知関連テーブル

- `service_notification_states`
  各 service の直近状態を持ち、fail / recovery の判定と重複通知抑制に使います。
- `project_notification_channels`
  project ごとの通知先設定を持ちます。現在は `log` / `webhook` / `discord` を扱えます。

## セットアップ

### 1. 環境変数ファイルを作成

```powershell
Copy-Item .env.example .env
```

必要に応じて [`.env.example`](D:\kozinn\.env.example) を見ながら [`.env`](D:\kozinn\.env) を編集してください。

### 2. Docker で起動

```powershell
docker compose up -d --build
```

### 3. マイグレーション適用

```powershell
docker compose exec api alembic upgrade head
```

### 4. API 確認

- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- Health Check: [http://localhost:8000/health](http://localhost:8000/health)

### 5. worker ログ確認

```powershell
docker compose logs -f worker
```

## よく使うコマンド

### 全体起動

```powershell
docker compose up -d --build
```

### 停止

```powershell
docker compose down
```

### マイグレーション適用

```powershell
docker compose exec api alembic upgrade head
```

### API ログ

```powershell
docker compose logs -f api
```

### worker ログ

```powershell
docker compose logs -f worker
```

### retention を手動実行

```powershell
docker compose exec worker python -m worker.retention_job
```

## API 一覧

### Auth

- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`

### Projects

- `POST /projects`
- `GET /projects`
- `GET /projects/{project_id}`

### Members

- `POST /projects/{project_id}/members`
- `GET /projects/{project_id}/members`

### Services

- `POST /projects/{project_id}/services`
- `GET /projects/{project_id}/services`
- `GET /services/{service_id}`
- `PATCH /services/{service_id}`

### Checks

- `GET /services/{service_id}/checks`
- `GET /projects/{project_id}/dashboard`

### Notification Channels

- `POST /projects/{project_id}/notification-channels`
- `GET /projects/{project_id}/notification-channels`
- `PATCH /projects/{project_id}/notification-channels/{channel_id}`

## 監視仕様

worker は以下のルールで監視します。

- `services.is_active = true` の service のみ対象
- 実行間隔は `MONITOR_INTERVAL_SECONDS` 秒
- HTTP メソッドは GET
- timeout は `REQUEST_TIMEOUT_SECONDS` 秒
- HTTP `200-399` を success
- それ以外と例外を fail
- 結果は `check_results` に保存

保存される主な値:

- `service_id`
- `is_success`
- `status_code`
- `response_time_ms`
- `error_message`
- `checked_at`

## Dashboard API について

`GET /projects/{project_id}/dashboard` は MVP 向けに軽量化しています。

- project 配下の service 一覧を返す
- 各 service の `latest_check` は最新 1 件だけ返す
- 稼働率集計や長期履歴集計はまだ行わない

これにより、`check_results` が増えても dashboard を比較的軽く保ちやすくしています。

## Retention について

`check_results` は 1 分ごとに増えるため、MVP では一定日数より古いデータを削除する retention を入れています。

- 保持期間は `CHECK_RESULTS_RETENTION_DAYS`
- cleanup 実行間隔は `RETENTION_CLEANUP_INTERVAL_HOURS`
- worker 内で定期実行
- 必要なら `python -m worker.retention_job` で単体実行可能

将来的には ECS Scheduled Task / EventBridge に切り出しやすい構成です。

## 通知機能

現在の通知機能では、service の状態変化に応じて通知します。

- fail した最初のタイミングで通知
- fail が続いても毎分通知しない
- 復旧したタイミングで recovery 通知

### 通知の仕組み

- worker は監視結果を保存
- `service_notification_states` を見て状態変化を判定
- `project_notification_channels` から通知先を取得
- `Notifier` 抽象に従った notifier 実装が送信

worker は notifier を呼ぶだけで、Discord への HTTP 送信処理は notifier 実装側に閉じています。

### 現在の通知チャネル

- `log`
  worker ログに通知内容を出します。
- `discord`
  Discord Webhook に通知します。
- `webhook`
  汎用 webhook 用です。

### Discord 通知

Discord 通知は embeds 形式で送信します。  
現在は以下の情報を含みます。

- project_name
- service_name
- status
- environment
- checked_at
- response_time_ms
- status_code
- error_message（fail 時のみ）

### Discord 通知の設定

`.env` に Webhook URL を設定します。

```env
NOTIFICATION_DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

project に通知チャネルを登録する例:

```json
{
  "channel_type": "discord",
  "display_name": "discord-main",
  "secret_ref": "NOTIFICATION_DISCORD_WEBHOOK_URL",
  "is_enabled": true
}
```

`secret_ref` には Webhook URL そのものではなく、環境変数名を入れます。

### Discord 通知の確認手順

1. `.env` に `NOTIFICATION_DISCORD_WEBHOOK_URL` を設定
2. `docker compose up -d --build` で再起動
3. Swagger で `POST /projects/{project_id}/notification-channels` を実行
4. `PATCH /services/{service_id}` で service の URL を壊す
5. worker が fail を検知すると Discord に failure 通知
6. URL を戻すと recovery 通知

失敗時の確認:

```powershell
docker compose logs -f worker
docker compose exec worker env | findstr NOTIFICATION_DISCORD_WEBHOOK_URL
```

## 主な環境変数

### アプリ / DB

- `APP_NAME`
- `APP_ENV`
- `APP_DEBUG`
- `SECRET_KEY`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `DATABASE_URL`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- `POSTGRES_HOST`
- `POSTGRES_PORT`

### 監視 / retention

- `MONITOR_INTERVAL_SECONDS`
- `REQUEST_TIMEOUT_SECONDS`
- `CHECK_RESULTS_RETENTION_DAYS`
- `RETENTION_CLEANUP_INTERVAL_HOURS`
- `RETENTION_DELETE_BATCH_SIZE`

### 通知

- `NOTIFICATION_BACKEND`
- `NOTIFICATION_WEBHOOK_URL`
- `NOTIFICATION_DISCORD_WEBHOOK_URL`
- `NOTIFICATION_TIMEOUT_SECONDS`

## 現時点の制約

- 通知履歴テーブル `notification_events` はまだない
- Slack / SNS は未対応
- インシデント管理は未実装
- 通知ルールはシンプルで、細かな条件分岐はまだない

## 今後の候補

- Discord 通知の見た目改善
- 通知履歴の保存
- Slack 対応
- インシデント管理
- 監査ログ
- ECS / Fargate 前提の運用整理
