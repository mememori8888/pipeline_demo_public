# Pipeline Demo 実装・公開レポート

作成日: 2026-07-29  
対象リポジトリ: `mememori8888/pipeline_demo_public`  
対象アプリ: FastAPI / Google Drive 入出力 / Gemini 処理パイプライン

## 1. 最終状態

ブラウザで使える簡易操作画面付きのアプリとして公開済み。

- 公開URL: `https://34.84.106.184.sslip.io/`
- Health check: `https://34.84.106.184.sslip.io/api/healthz`
- API docs: `https://34.84.106.184.sslip.io/api/docs`
- GitHub repository: `https://github.com/mememori8888/pipeline_demo_public`

処理 API は `X-API-Key` で保護している。ブラウザ画面の `API Key` 欄には、ローカル `.env` の `APP_API_KEY` を入力する。

## 2. 何を作ったか

### FastAPI の CI 対応

GitHub Actions 用に `.github/workflows/ci.yml` を追加した。

CI では次を検証する。

- Python 3.12 のセットアップ
- `requirements.txt` のインストール
- `python -m compileall app`
- FastAPI app の import
- Uvicorn 起動と health check
- Dockerfile の build

Secrets なしでも CI が通るよう、CI では dummy 環境変数を使う。

### Health check

FastAPI に軽量な health endpoint を追加した。

- `GET /healthz`
- `GET /api/healthz`

レスポンス:

```json
{"status":"ok","service":"pipeline_demo"}
```

### Google Drive 入出力

Google Drive の入力フォルダと出力フォルダを分けて使う構成にした。

- 入力フォルダ ID: `1kMyHqOVEwzqMmwncRAZDe_rKqi5rW9O2`
- 出力フォルダ ID: `17zq5NSZemu11yIe6QnwMP_sxakCIOZma`

`POST /api/v1/document/batch-process` は、デフォルトで `storage_type=google_drive` として動く。

画面または API で `target_path` と `output_folder_id` を空にすると、Cloud/VM の環境変数に設定された Drive フォルダ ID を使う。

### Drive 接続確認 API

操作画面から Drive 接続状態を確認するため、次の endpoint を追加した。

- `GET /api/v1/drive/status`

確認できる内容:

- 入力フォルダ名
- 入力フォルダの読み取り可否
- 入力フォルダ内のサンプルファイル
- 出力フォルダ名
- 出力フォルダへの追加可否

### API キー保護

公開 URL にした場合でも Gemini や Drive 操作を誰でも実行できないよう、処理系 endpoint に `X-API-Key` 認証を追加した。

対象:

- `GET /api/v1/drive/status`
- `POST /api/v1/schema/generate`
- `POST /api/v1/document/process`
- `POST /api/v1/document/decrypt`
- `POST /api/v1/document/batch-process`
- `POST /api/v1/document/youtube-channel-process`

キーなしの場合は `401` を返す。

### ブラウザ操作画面

`app/ui.py` を追加し、FastAPI の `/` と `/app` で操作画面を表示するようにした。

画面でできること:

- API Key をブラウザに保存
- Drive 接続確認
- Google Drive batch 処理開始
- 処理件数指定
- prompt preset 選択
- custom prompt 入力
- 入力フォルダ/出力フォルダ/API Docs へのリンク

## 3. インフラ構成

### Cloud Run

Cloud Run にはデプロイ済み。

- Project: `geoai-cloudrun`
- Region: `asia-northeast1`
- Service: `pipeline-demo-api`
- Latest verified revision: `pipeline-demo-api-00004-9ff`
- Runtime service account: `drive-batch-operator@geoai-cloudrun.iam.gserviceaccount.com`

Cloud Run サービス自体は private のまま。

理由:

- 現在使えるサービスアカウントでは `run.services.setIamPolicy` が不足していた
- `--allow-unauthenticated` と `--no-invoker-iam-check` の両方が権限不足で失敗した

### 公開 URL

Cloud Run の直接公開が権限不足で止まったため、同じコンテナイメージを Compute Engine VM で起動し、Caddy で HTTPS 化して公開した。

- VM name: `pipeline-demo-public-vm`
- Zone: `asia-northeast1-b`
- Machine type: `e2-micro`
- Static IP resource: `pipeline-demo-vm-ip`
- Public IP: `34.84.106.184`
- HTTPS URL: `https://34.84.106.184.sslip.io/`
- Firewall: `pipeline-demo-allow-https`
- HTTPS reverse proxy: Caddy container `pipeline-demo-caddy`

外部 HTTP port 80 は閉じ、外部公開は HTTPS port 443 のみにした。VM 内部では Caddy が `127.0.0.1:80` の FastAPI コンテナへ reverse proxy する。

### 不要リソースの片付け

Cloud Run の前段に Load Balancer + serverless NEG を試したが、Cloud Run 側の private 認証チェックにより目的を満たせなかった。

作成後、次の一時リソースは削除済み。

- `pipeline-demo-http-rule`
- `pipeline-demo-http-proxy`
- `pipeline-demo-url-map`
- `pipeline-demo-backend`
- `pipeline-demo-neg`
- `pipeline-demo-lb-ip`

## 4. 使い方

1. `https://34.84.106.184.sslip.io/` を開く
2. `API Key` に `.env` の `APP_API_KEY` を入力する
3. `保存` を押す
4. `Drive確認` を押す
5. 入力 Drive フォルダに PDF / 画像 / txt を入れる
6. `処理件数` を指定する
7. `処理開始` を押す
8. `出力を開く` から出力 Drive フォルダを確認する

初回テストでは `処理件数=1` にすると安全。

## 5. 検証結果

実施済みの確認:

- GitHub Actions CI: success
- 公開 HTTPS URL の `/` が操作画面を返す
- `GET /api/healthz`: `200`
- `GET /api/v1/drive/status` キーなし: `401`
- `GET /api/v1/drive/status` キーあり: `200`
- Drive 入力フォルダ名: `PDFinput`
- Drive 出力フォルダ名: `PDFoutput`
- 出力フォルダへの追加権限: OK
- 公開 URL から batch 実行: `200 accepted`
- 出力 Drive フォルダに Markdown 作成: 成功

検証で生成された出力例:

- `integrated_book_analysis_1d3307de.md`
- `integrated_book_analysis_79b55299.md`

検証用に入力フォルダへ置いた txt ファイルは処理後に trash 済み。出力 Markdown は証跡として残している。

## 6. GitHub に反映した主な commit

- `Use ADC for Cloud Run Drive auth`
- `Harden Cloud Run environment handling`
- `Add API health endpoint for Cloud Run`
- `Make Cloud Run API usable with API key auth`
- `Add Cloud Run usage scripts`
- `Add browser operator console`
- `Document public operator console`
- `Update docs with HTTPS public URL`

## 7. 注意点

### 秘密情報

以下の実値は repository に入れない。

- `GEMINI_API_KEY`
- `YOUTUBE_API_KEY`
- `ENCRYPTION_KEY`
- `APP_API_KEY`
- `service_account.json`

GitHub Actions 用には GitHub Secrets を使う。VM / Cloud Run では環境変数として渡している。

### API キーのローテーション

作業中に Cloud Run の設定確認などで一部環境変数がコマンド出力に表示された可能性がある。実運用では Gemini / YouTube / APP API key のローテーションを推奨する。

### Cloud Run 直公開に戻す場合

Cloud Run を直接公開したい場合は、デプロイに使うアカウントへ `run.services.setIamPolicy` を含む権限を付与する。

その後、次を実行する。

```powershell
gcloud run services add-iam-policy-binding pipeline-demo-api `
  --project geoai-cloudrun `
  --region asia-northeast1 `
  --member=allUsers `
  --role=roles/run.invoker
```

または Cloud Console で `Allow unauthenticated invocations` を有効化する。

### 独自ドメイン

現在は `sslip.io` の一時ドメインを使っている。正式運用では独自ドメインを取得し、Caddy または Cloud Load Balancer に証明書を設定するのが望ましい。

## 8. 復習ポイント

今回の流れを復習するときは、次の順で見ると理解しやすい。

1. FastAPI アプリに health endpoint を追加した
2. GitHub Actions で import / health / Docker build を検証した
3. Google Drive 入力と出力を環境変数化した
4. Drive 接続 API を追加した
5. 公開に備えて処理 endpoint を `X-API-Key` で保護した
6. `/` にブラウザ操作画面を追加した
7. Cloud Run へデプロイした
8. Cloud Run の公開 IAM が不足していることを確認した
9. 同じコンテナを Compute Engine VM へ載せた
10. Caddy + `sslip.io` で HTTPS 公開した
11. 公開 URL から Drive batch が実際に完走することを確認した

## 9. 次にやるとよいこと

- 独自ドメインへ切り替える
- Secret Manager 参照に戻す
- API キーをローテーションする
- Cloud Run 直公開用の IAM 権限を整える
- 出力ファイル一覧を画面内に直接表示する
- 処理ジョブの進捗管理を追加する
- VM の月額コストを見て、必要なら Cloud Run 直公開へ戻す
