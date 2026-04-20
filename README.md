# Monitoring MVP Backend

チーム向けサービス監視ツールの MVP バックエンドです。

FastAPI を API 層、PostgreSQL を永続化層、worker を監視実行層として分離し、ローカル Docker で動作確認できる構成にしています。現時点では AWS 固有の実装は入れておらず、将来 `ECS/Fargate + RDS + EventBridge Scheduler + Secrets Manager / SSM` に移しやすいように、監視・通知・incident・secret 解決の責務を分離しています。

## 技術スタック

- Python
- FastAPI
- PostgreSQL
- SQLAlchemy 2.x
- Alembic
- JWT
- Docker / docker-compose
- httpx

## できていること

- ユーザー登録 / ログイン / JWT 認証
- project 作成 / 一覧 / 詳細取得
- project member 管理
- service 登録 / 一覧 / 更新
- worker による定期監視
- `check_results` 保存
- dashboard API
- retention による古い `check_results` 削除
- project 単位の notification channel 管理
- log notifier / webhook notifier / Discord notifier
- failure / recovery / 重複抑制の通知制御
- `notification_events` 保存
- `incidents` 管理
- `notification_events` 一覧 API
- `incidents` 一覧 API

## アーキテクチャ

- `api`
  FastAPI ベースの API サーバーです。認証、project / service / notification channel 管理、dashboard、参照系 API を担当します。
- `worker`
  1 分ごとに service を監視し、`check_results` 保存、incident reconcile、通知オーケストレーション、retention 実行を担当します。
- `db`
  PostgreSQL です。アプリケーションデータと監視結果を保存します。

API と worker は分離しており、worker は API の詳細や通知先ごとの実装詳細を知りません。worker は「監視結果を保存し、incident と通知の処理を呼ぶ」ことに集中し、通知の詳細は通知層に閉じ込めています。

## 主要ディレクトリ

```text
.
├─ alembic/
├─ app/
│  ├─ api/
│  │  ├─ deps.py
│  │  ├─ router.py
│  │  └─ routes/
│  ├─ core/
│  ├─ db/
│  ├─ models/
│  ├─ schemas/
│  ├─ services/
│  └─ main.py
├─ worker/
│  ├─ main.py
│  ├─ incidents.py
│  ├─ notifications.py
│  ├─ retention.py
│  ├─ retention_job.py
│  └─ secrets.py
├─ docker-compose.yml
├─ Dockerfile
└─ requirements.txt
```

## worker の責務分割

### `worker/main.py`

- 監視ループ全体の起点
- アクティブな service の取得
- HTTP チェック実行
- `check_results` 保存
- `reconcile_incident_state` 呼び出し
- `evaluate_and_send_notification` 呼び出し
- retention 実行タイミングの管理

### `worker/incidents.py`

- service ごとの incident open / close 判定
- open incident の取得
- `success -> fail` で incident open
- `fail -> success` で incident close
- fail 継続中に incident を増やさない制御

### `worker/notifications.py`

- 通知要否の判定
- failure / recovery の判定
- 重複抑制
- `notification_events` の `pending / sent / failed` 管理
- channel ごとの notifier 切り替え
- Discord 429 rate limit の再試行

### `worker/secrets.py`

- secret 解決の抽象化
- 現状は環境変数からの解決
- 将来 Secrets Manager / SSM adapter を追加しやすい境界

## データモデル

### 基本テーブル

- `users`
- `projects`
- `project_members`
- `services`
- `check_results`
- `service_notification_states`
- `project_notification_channels`

### 追加済みテーブル

#### `notification_events`

目的:
通知が発生した事実と送信結果を履歴として保存するためのテーブルです。

主なカラム:

- `project_id`
- `service_id`
- `channel_id`
- `check_result_id`
- `channel_type`
- `channel_display_name`
- `event_type`
- `delivery_status`
- `error_message`
- `delivered_at`
- `created_at`
- `updated_at`

保存フロー:

1. 通知対象になったら channel ごとに `pending` を作成
2. notifier が送信
3. 成功で `sent`
4. 失敗で `failed` と `error_message` を保存

notifier は送信だけを担当し、DB 保存責務は通知オーケストレーション側が持ちます。

#### `incidents`

目的:
service 障害の open / close を履歴として残すためのテーブルです。

主なカラム:

- `project_id`
- `service_id`
- `opened_check_result_id`
- `closed_check_result_id`
- `title`
- `status`
- `opened_at`
- `closed_at`
- `created_at`
- `updated_at`

ルール:

- `success -> fail` で open
- fail 継続中は新しい incident を増やさない
- `fail -> success` で open incident を close
- service ごとに同時 open incident は 1 件まで
- PostgreSQL の部分ユニークインデックスで補強

## 通知設計

- worker は通知の詳細を知らず、通知オーケストレーションを呼ぶだけです
- `Notifier` 抽象を維持しています
- `channel_type` ごとに notifier 実装を切り替えます
- Discord は embeds 形式で送信します
- Discord 429 rate limit は `Retry-After` に従って再試行します
- secret 解決は resolver に分けています
- 通知失敗時も worker 全体は止めません

### 通知失敗時の方針

通知送信に失敗しても、監視ループ全体は停止しません。

- `worker/notifications.py` では channel ごとに `notification_events` を更新します
- 送信失敗時は `delivery_status=failed` と `error_message` を保存します
- `worker/main.py` 側でも例外はロールバックしてログ出力し、次の service 監視を継続します

このため、「監視そのもの」と「通知送信失敗」は切り分けて扱えます。

## incident lifecycle

- 正常時は incident なし
- `success -> fail` の変化点で incident を open
- fail が続いても open incident を増やさない
- `fail -> success` の変化点で同じ incident を close

通知と incident は連携しますが、責務は分離しています。

- incident は障害状態の履歴
- `notification_events` は通知送信履歴

## 参照系 API

### Notification Events

- `GET /projects/{project_id}/notification-events`

query:

- `service_id`
- `delivery_status`
- `event_type`
- `limit`
- `offset`

挙動:

- `created_at desc` で返却
- project 認可あり
- 自分が所属していない project は `403`

### Incidents

- `GET /projects/{project_id}/incidents`

query:

- `status`
- `service_id`
- `limit`
- `offset`

挙動:

- `opened_at desc` で返却
- project 認可あり
- 自分が所属していない project は `403`

## セットアップ

### 1. 環境変数ファイルを作成

```powershell
Copy-Item .env.example .env
```

必要に応じて `DATABASE_URL` や Discord 用の環境変数を編集してください。

### 2. コンテナ起動

```powershell
docker compose up -d --build
```

### 3. migration 適用

```powershell
docker compose exec api alembic upgrade head
```

### 4. 動作確認

- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- Health Check: [http://localhost:8000/health](http://localhost:8000/health)

### 5. ログ確認

```powershell
docker compose logs -f api
docker compose logs -f worker
```

## よく使うコマンド

### 起動

```powershell
docker compose up -d --build
```

### 停止

```powershell
docker compose down
```

### migration 適用

```powershell
docker compose exec api alembic upgrade head
```

### retention 単発実行

```powershell
docker compose exec worker python -m worker.retention_job
```

## 実データ確認手順

MVP の最終確認として、参照系 API と incident lifecycle は以下の順で確認できます。

### 0. 準備するデータ

1. user A を登録してログインする
2. user B を登録してログインする
3. user A で project を作成する
4. user A で service を 1 件以上作成する
5. 必要に応じて project notification channel を追加する

### 1. 403 認可ケースの確認

確認対象:

- `GET /projects/{project_id}/notification-events`
- `GET /projects/{project_id}/incidents`

手順:

1. user A で project を作成する
2. user B はその project に member 追加しない
3. user B の JWT で以下を呼ぶ

```http
GET /projects/{project_id}/notification-events
GET /projects/{project_id}/incidents
```

期待結果:

- どちらも `403 Forbidden`
- response detail は `Project access denied`

実装根拠:

- `app/api/deps.py` の `require_project_member`

### 2. open incident がある状態で `status=open` を確認

手順:

1. 成功している service を 1 件用意する
2. その service の URL を失敗する URL に更新する
3. worker が 1 回監視を実行するまで待つ
4. 以下を呼ぶ

```http
GET /projects/{project_id}/incidents?status=open
```

期待結果:

- 該当 service の incident が 1 件返る
- `status=open`
- `closed_at=null`
- `closed_check_result_id=null`

実装根拠:

- `worker/incidents.py`
- `app/services/notification_queries.py`

### 3. fail 継続中に incident が増えないことを確認

手順:

1. open incident がある状態を作る
2. service を fail のまま維持する
3. worker の監視サイクルを複数回待つ
4. 以下を呼ぶ

```http
GET /projects/{project_id}/incidents?status=open
```

期待結果:

- open incident は増えない
- 同じ service に対して open incident は 1 件のまま

### 4. recovery で incident が close されることを確認

手順:

1. open incident がある service の URL を正常な URL に戻す
2. worker が 1 回監視を実行するまで待つ
3. 以下を呼ぶ

```http
GET /projects/{project_id}/incidents?status=closed
```

期待結果:

- 同じ incident が `closed` になって返る
- `closed_at` が入る
- `closed_check_result_id` が入る

### 5. incidents API の `service_id` フィルタ確認

手順:

1. 同一 project に service を 2 件以上作る
2. 片方の service だけ incident を発生させる
3. 以下を呼ぶ

```http
GET /projects/{project_id}/incidents?service_id={service_id}
```

期待結果:

- 指定した `service_id` の incident だけ返る
- 別 service の incident は返らない

### 6. notification_events API の履歴確認

手順:

1. fail を発生させる
2. recovery を発生させる
3. 以下を呼ぶ

```http
GET /projects/{project_id}/notification-events
GET /projects/{project_id}/notification-events?event_type=failure
GET /projects/{project_id}/notification-events?delivery_status=failed
GET /projects/{project_id}/notification-events?service_id={service_id}
```

期待結果:

- channel ごとに 1 件ずつ event が保存される
- success 時は `delivery_status=sent`
- 失敗時は `delivery_status=failed` と `error_message` が確認できる
- `created_at desc` で並ぶ

## cURL / PowerShell での確認例

Swagger でも確認できますが、再現性を高めるために API 呼び出し例を残します。

### ログイン

```powershell
$loginBody = @{
  email = "owner@example.com"
  password = "password1234"
} | ConvertTo-Json

$token = (
  Invoke-RestMethod `
    -Method Post `
    -Uri "http://localhost:8000/auth/login" `
    -ContentType "application/json" `
    -Body $loginBody
).access_token
```

### incidents 一覧

```powershell
Invoke-RestMethod `
  -Method Get `
  -Uri "http://localhost:8000/projects/1/incidents?status=open" `
  -Headers @{ Authorization = "Bearer $token" }
```

### notification_events 一覧

```powershell
Invoke-RestMethod `
  -Method Get `
  -Uri "http://localhost:8000/projects/1/notification-events?event_type=failure" `
  -Headers @{ Authorization = "Bearer $token" }
```

## AWS で差し替える想定ポイント

現時点ではローカル Docker 前提ですが、以下の境界は将来の AWS 移行を見据えています。

- worker 実行基盤
  現状は Docker 上の常駐 worker。将来は ECS/Fargate や Scheduled Task に置き換えやすいです。
- DB
  現状は PostgreSQL コンテナ。将来は RDS に移行しやすいです。
- スケジューラ
  現状は worker 内のループ。将来は EventBridge Scheduler や Scheduled Task に置き換えやすいです。
- secret 解決
  現状は環境変数。将来は Secrets Manager / SSM adapter を `worker/secrets.py` に追加しやすいです。
- notifier
  `Notifier` 抽象を保っているため、Slack や SNS などの通知先追加がしやすいです。

## 既知の補足

- PowerShell の表示設定によって README が文字化けして見える場合があります
- Docker Desktop / WSL の D ドライブマウントに起因する一時エラーが出ることがあります
- ローカル確認時は `docker compose logs -f api` と `docker compose logs -f worker` を併用すると追跡しやすいです

## 次の候補

- Slack notifier 追加
- 監査ログ
- incident 一覧 / notification 履歴の UI 化
- API / worker の自動テスト拡充
