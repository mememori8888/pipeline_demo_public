# Pipeline Demo 実装・公開レポート

作成日: 2026-07-29  
対象リポジトリ: `mememori8888/pipeline_demo_public`  
対象アプリ: FastAPI / Google Drive 入出力 / Gemini 処理パイプライン

## 1. 最終状態

ブラウザで使える簡易操作画面付きのアプリとして公開済み。

- 公開URL: `https://pipeline-demo-api-xebbfpgofa-an.a.run.app/`
- Health check: `https://pipeline-demo-api-xebbfpgofa-an.a.run.app/api/healthz`
- API docs: `https://pipeline-demo-api-xebbfpgofa-an.a.run.app/api/docs`
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

画面または API で `target_path` と `output_folder_id` を空にすると、Cloud Run の環境変数に設定された Drive フォルダ ID を使う。

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
- 処理件数指定（空欄なら全件）
- 分割サイズ指定
- prompt preset 選択
- custom prompt 入力
- 入力フォルダ/出力フォルダ/API Docs へのリンク

### 大量ファイルの分割統合

大量ファイルを1回の最終出力だけにすると、途中で止まった場合に成果物が残らない。そのため、batch 処理は分割統合方式に変更した。

- `batch_<job_id>_part_001_integrated.md` のような分割統合ファイルを順次 Drive に保存する
- 最後に `batch_<job_id>_final_integrated.md` を保存する
- final は短いサマリーではなく、分割統合ファイル群をさらに読み合わせた統合原稿として生成する
- Gemini 呼び出しには timeout を設定し、固まった場合は error Markdown を Drive に残す
- 低負荷運用のため、Gemini page analysis は同時実行 `1`、分割サイズ `3`、ファイル間 `3秒`、分割間 `15秒` の待機を標準にする

### 補助スクリプト

`scripts/cloudrun_drive_status.ps1` と `scripts/cloudrun_batch_start.ps1` は、Cloud Run の公開 URL に直接アクセスする形へ更新した。通常利用では `gcloud auth` や identity token は不要で、ローカル `.env` の `APP_API_KEY` だけを使う。

## 3. インフラ構成

### Cloud Run

Cloud Run にデプロイ済みで、現在の公開経路は Cloud Run のみ。

- Project: `geoai-cloudrun`
- Region: `asia-northeast1`
- Service: `pipeline-demo-api`
- Latest verified revision: `pipeline-demo-api-00008-kjk`
- Runtime service account: `drive-batch-operator@geoai-cloudrun.iam.gserviceaccount.com`
- Public URL: `https://pipeline-demo-api-xebbfpgofa-an.a.run.app/`
- Large batch settings: timeout `3600s`, memory `1Gi`, concurrency `1`, max instances `1`

ユーザー側で Cloud Run の `Allow public access` を有効化した後、認証なしの health check と API キー付き Drive 接続確認が Cloud Run 直で成功した。

### 旧公開 URL

Cloud Run の直接公開が権限不足で止まっていた期間は、同じコンテナイメージを Compute Engine VM で起動し、Caddy で HTTPS 化して一時公開した。

- VM name: `pipeline-demo-public-vm`
- Zone: `asia-northeast1-b`
- Machine type: `e2-micro`
- Static IP resource: `pipeline-demo-vm-ip`
- Public IP: `34.84.106.184`
- HTTPS URL: `https://34.84.106.184.sslip.io/`
- Firewall: `pipeline-demo-allow-https`
- HTTPS reverse proxy: Caddy container `pipeline-demo-caddy`

Cloud Run 直公開が通った後、この一時 VM、固定 IP、firewall は削除済み。現在は `sslip.io` の旧 URL は使わない。

### 不要リソースの片付け

Cloud Run の前段に Load Balancer + serverless NEG を試したが、Cloud Run 側の private 認証チェックにより目的を満たせなかった。

作成後、次の一時リソースは削除済み。

- `pipeline-demo-http-rule`
- `pipeline-demo-http-proxy`
- `pipeline-demo-url-map`
- `pipeline-demo-backend`
- `pipeline-demo-neg`
- `pipeline-demo-lb-ip`
- `pipeline-demo-public-vm`
- `pipeline-demo-vm-ip`
- `pipeline-demo-allow-https`

## 4. 使い方

1. `https://pipeline-demo-api-xebbfpgofa-an.a.run.app/` を開く
2. `API Key` に `.env` の `APP_API_KEY` を入力する
3. `保存` を押す
4. `Drive確認` を押す
5. 入力 Drive フォルダに PDF / 画像 / txt を入れる
6. 全件処理する場合は `処理件数` を空欄にする
7. `処理開始` を押す
8. `出力を開く` から出力 Drive フォルダを確認する
9. 処理中は `batch_<job_id>_part_XXX_integrated.md`、完了時は `batch_<job_id>_final_integrated.md` を確認する

分割サイズは通常 `3` のままでよい。92件なら、おおむね31個の part ファイルと1個の final ファイルが出る。時間はかかるが、Gemini と Cloud Run への瞬間負荷を抑える。

## 5. 検証結果

実施済みの確認:

- GitHub Actions CI: success
- Cloud Run 公開 URL の `/` が操作画面を返す
- `GET /api/healthz`: `200`
- `GET /api/v1/drive/status` キーなし: `401`
- `GET /api/v1/drive/status` キーあり: `200`
- Drive 入力フォルダ名: `PDFinput`
- Drive 出力フォルダ名: `PDFoutput`
- 出力フォルダへの追加権限: OK
- 公開 URL から batch 実行: `200 accepted`
- 出力 Drive フォルダに Markdown 作成: 成功
- 一時 VM / 固定 IP / firewall: 削除済み

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
- `Add implementation review report`
- `Switch docs and scripts to Cloud Run-only public URL`
- `Add chunked integration outputs for large Drive batches`
- `Add Gemini timeout guard for Drive batch integrations`
- `Throttle Drive batch processing for low-load operation`

## 7. 注意点

### 秘密情報

以下の実値は repository に入れない。

- `GEMINI_API_KEY`
- `YOUTUBE_API_KEY`
- `ENCRYPTION_KEY`
- `APP_API_KEY`
- `service_account.json`

GitHub Actions 用には GitHub Secrets を使う。Cloud Run では環境変数として渡している。

### API キーのローテーション

作業中に Cloud Run の設定確認などで一部環境変数がコマンド出力に表示された可能性がある。実運用では Gemini / YouTube / APP API key のローテーションを推奨する。

### Cloud Run 直公開

Cloud Console で `Allow public access` を有効化済み。以後の公開経路は Cloud Run URL を使う。

### 独自ドメイン

正式運用では独自ドメインを Cloud Run にマッピングする。現時点では Cloud Run 標準 URL を使う。

## 8. 復習ポイント

今回の流れを復習するときは、次の順で見ると理解しやすい。

1. FastAPI アプリに health endpoint を追加した
2. GitHub Actions で import / health / Docker build を検証した
3. Google Drive 入力と出力を環境変数化した
4. Drive 接続 API を追加した
5. 公開に備えて処理 endpoint を `X-API-Key` で保護した
6. `/` にブラウザ操作画面を追加した
7. Cloud Run へデプロイした
8. 当初は Cloud Run の公開 IAM が不足していたため、一時的に VM + Caddy で公開した
9. ユーザー側で Cloud Run の public access を有効化した
10. Cloud Run 直の URL で health / Drive 接続を確認した
11. 一時 VM / 固定 IP / firewall を削除して Cloud Run のみに戻した
12. 補助スクリプトとドキュメントを Cloud Run 公開 URL 前提に更新した
13. 大量ファイル向けに、分割統合ファイルと最終統合ファイルを Drive に順次保存する方式へ変更した

## 9. 次にやるとよいこと

- 独自ドメインへ切り替える
- Secret Manager 参照に戻す
- API キーをローテーションする
- 出力ファイル一覧を画面内に直接表示する
- 処理ジョブの進捗管理を追加する
