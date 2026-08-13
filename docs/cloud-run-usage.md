# Cloud Run Usage

For the full implementation history and review notes, see `docs/implementation-report-2026-07-29.md`.

## URL

- Public operator console: `https://pipeline-demo-api-xebbfpgofa-an.a.run.app/`
- Public health check: `https://pipeline-demo-api-xebbfpgofa-an.a.run.app/api/healthz`
- API docs: `https://pipeline-demo-api-xebbfpgofa-an.a.run.app/api/docs`

The app is now served directly by Cloud Run. The temporary Compute Engine + Caddy public endpoint has been removed.

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
  https://pipeline-demo-api-xebbfpgofa-an.a.run.app/api/v1/drive/status
```

## Google Drive Batch Processing

1. Put PDFs, images, or text files into the configured input Drive folder.
2. Open `/api/docs`.
3. Authorize with `X-API-Key`.
4. Run `POST /api/v1/document/batch-process`.
5. Leave `storage_type` as `google_drive`.
6. Leave `target_path` and `output_folder_id` blank to use Cloud Run environment defaults.
7. Leave `limit_count` blank to process every supported file in the input folder, or set it only when you intentionally want to cap the run.
8. Use `chunk_size=5` unless you have a reason to change the batch size.
9. Check the configured output Drive folder for generated Markdown files.

Large runs are written in stages:

- `batch_<job_id>_part_001_integrated.md`, `batch_<job_id>_part_002_integrated.md`, ... are uploaded as each chunk finishes.
- `batch_<job_id>_final_integrated.md` is uploaded at the end. This is an integrated document built from the split integrated files, not a short summary.

The operator console at `https://pipeline-demo-api-xebbfpgofa-an.a.run.app/` provides the same flow with buttons:

1. Paste `APP_API_KEY`.
2. Click `保存`.
3. Click `Drive確認`.
4. Leave `処理件数` blank for all files, or set it only when you need a cap.
5. Click `処理開始`.
6. Click `出力を開く`.

## Helper Scripts

The helper scripts call the public Cloud Run URL directly and only require `APP_API_KEY` in the local env file.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\cloudrun_drive_status.ps1
powershell -ExecutionPolicy Bypass -File scripts\cloudrun_batch_start.ps1 -ChunkSize 5
```

## Useful Endpoints

- `GET /api/v1/drive/status`: confirms the service account can see the input folder and write to the output folder.
- `POST /api/v1/document/batch-process`: starts Google Drive document processing in the background.
- `POST /api/v1/document/youtube-channel-process`: starts YouTube channel report generation in the background.
