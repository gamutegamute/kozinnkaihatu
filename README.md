# Monitoring MVP Backend

FastAPI + PostgreSQL + SQLAlchemy + Alembic で構成した、チーム向けサービス監視ツールのMVPバックエンドです。

## 採用方針

- ORM は SQLAlchemy 2.x を採用
- 理由は Alembic との相性が安定しており、FastAPI での実績も多く、将来 ECS/Fargate + RDS に載せる際の拡張性が高いため
- 認証は JWT Bearer トークン
- 認可は「所属プロジェクトのみアクセス可」「メンバー追加は owner のみ」

## ディレクトリ構成

```text
.
├── alembic
│   ├── env.py
│   ├── script.py.mako
│   └── versions
│       └── 0001_initial.py
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
│   │   ├── member.py
│   │   ├── project.py
│   │   ├── service.py
│   │   └── user.py
│   └── main.py
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

### 3. マイグレーション適用

```bash
docker compose exec api alembic upgrade head
```

### 4. API ドキュメント確認

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health Check: http://localhost:8000/health

## ローカル開発コマンド

```bash
docker compose up --build
docker compose exec api alembic revision --autogenerate -m "message"
docker compose exec api alembic upgrade head
docker compose exec api alembic downgrade -1
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

## MVP の仕様メモ

- 監視実行ジョブ自体は未実装
- `check_results` は将来の定期実行保存先として先行作成
- 想定仕様は 1 分ごとの HTTP GET チェック
- timeout は 5 秒想定
- HTTP 200〜399 を成功とみなす前提
