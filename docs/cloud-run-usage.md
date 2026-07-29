# Cloud Run Usage

For the full implementation history and review notes, see `docs/implementation-report-2026-07-29.md`.

## URL

- Public operator console: `https://34.84.106.184.sslip.io/`
- Public health check: `https://34.84.106.184.sslip.io/api/healthz`
- Cloud Run service URL: `https://pipeline-demo-api-xebbfpgofa-an.a.run.app/`

The Cloud Run service itself is private because the current deployment service account does not have `run.services.setIamPolicy`. The public operator console is the same container image running on Compute Engine with the `drive-batch-operator` service account. HTTPS is terminated by Caddy on the VM using `sslip.io`.

## Authentication

Processing endpoints require an `X-API-Key` header.

In Swagger UI:

1. Open `/api/docs`.
2. Click `Authorize`.
3. Enter the value of `APP_API_KEY`.
4. Run the endpoint.

With curl:

```bash
curl -H "X-API-Key: $APP_API_KEY" \
  https://34.84.106.184.sslip.io/api/v1/drive/status
```

## Google Drive Batch Processing

1. Put PDFs, images, or text files into the configured input Drive folder.
2. Open `/api/docs`.
3. Authorize with `X-API-Key`.
4. Run `POST /api/v1/document/batch-process`.
5. Leave `storage_type` as `google_drive`.
6. Leave `target_path` and `output_folder_id` blank to use Cloud Run environment defaults.
7. Use `limit_count=1` for the first smoke test.
8. Check the configured output Drive folder for generated Markdown files.

The operator console at `https://34.84.106.184.sslip.io/` provides the same flow with buttons:

1. Paste `APP_API_KEY`.
2. Click `保存`.
3. Click `Drive確認`.
4. Set `処理件数`.
5. Click `処理開始`.
6. Click `出力を開く`.

## Useful Endpoints

- `GET /api/v1/drive/status`: confirms the service account can see the input folder and write to the output folder.
- `POST /api/v1/document/batch-process`: starts Google Drive document processing in the background.
- `POST /api/v1/document/youtube-channel-process`: starts YouTube channel report generation in the background.
