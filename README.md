# Monitoring MVP Backend

FastAPI + PostgreSQL + SQLAlchemy + Alembic で構成した、チーム向けサービス監視ツールのMVPバックエンドです。

## 採用方針

- ORM は SQLAlchemy 2.x を採用
- 理由は Alembic との相性が安定しており、FastAPI での実績も多く、将来 ECS/Fargate + RDS に載せる際の拡張性が高いため
- 認証は JWT Bearer トークン
- 認可は「所属プロジェクトのみアクセス可」「メンバー追加は owner のみ」
- 監視ワーカーは API と分離した別プロセス
- HTTP チェックは `httpx` の同期クライアントを採用
- retention は「一定日数より古い `check_results` を削除」で実装

## ディレクトリ構成

```text
.
├── alembic
│   ├── env.py
│   ├── script.py.mako
│   └── versions
│       ├── 0001_initial.py
│       └── 0002_add_check_results_latest_lookup_index.py
├── app
│   ├── api
│   │   ├── deps.py
│   │   ├── router.py
│   │   └── routes
│   │       ├── auth.py
│   │       ├── checks.py
│   │       ├── members.py
│   │       ├── projects.py
│   │       └── services.py
│   ├── core
│   │   ├── config.py
│   │   └── security.py
│   ├── db
│   │   ├── base.py
│   │   └── session.py
│   ├── models
│   │   ├── check_result.py
│   │   ├── project.py
│   │   ├── project_member.py
│   │   ├── service.py
│   │   └── user.py
│   ├── schemas
│   │   ├── auth.py
│   │   ├── check.py
│   │   ├── common.py
│   │   ├── member.py
│   │   ├── project.py
│   │   ├── service.py
│   │   └── user.py
│   └── main.py
├── worker
│   ├── Dockerfile
│   ├── main.py
│   ├── retention.py
│   └── retention_job.py
├── .env.example
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
├── README.md
└── requirements.txt
```

## セットアップ

### 1. 環境変数を用意

```bash
cp .env.example .env
```

PowerShell の場合:

```powershell
Copy-Item .env.example .env
```

### 2. Docker 起動

```bash
docker compose up --build
```

API / worker / DB を明示的に起動する場合:

```bash
docker compose up --build api worker db
```

### 3. マイグレーション適用

```bash
docker compose exec api alembic upgrade head
```

### 4. API ドキュメント確認

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health Check: http://localhost:8000/health

### 5. ワーカーログ確認

```bash
docker compose logs -f worker
```

## ローカル開発コマンド

```bash
docker compose up --build
docker compose exec api alembic upgrade head
docker compose logs -f worker
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

## Worker の仕様

- `services.is_active = true` のサービスだけを取得
- 60 秒ごとに `while True + sleep(60)` で監視を実行
- 各サービスに対して HTTP GET を実行
- timeout は 5 秒
- HTTP 200〜399 は success
- それ以外と例外は fail
- 結果は `check_results` に保存
- 例外時は `status_code = null`、`error_message` に例外内容を保存

## Retention の仕様

- MVP では `check_results` を 30 日保持
- 30 日より古い `check_results` は削除対象
- cleanup は worker 内で 24 時間ごとに実行
- 削除は一括ではなくバッチ単位で実行
- 後から `python -m worker.retention_job` を ECS scheduled task / EventBridge に切り出せる構成

## 主要な環境変数

- `MONITOR_INTERVAL_SECONDS=60`
- `REQUEST_TIMEOUT_SECONDS=5`
- `CHECK_RESULTS_RETENTION_DAYS=30`
- `RETENTION_CLEANUP_INTERVAL_HOURS=24`
- `RETENTION_DELETE_BATCH_SIZE=5000`
