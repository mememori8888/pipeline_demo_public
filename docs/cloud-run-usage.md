# Cloud Run Usage

## URL

- API docs: `https://pipeline-demo-api-xebbfpgofa-an.a.run.app/api/docs`
- Health check: `https://pipeline-demo-api-xebbfpgofa-an.a.run.app/api/healthz`

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
7. Use `limit_count=1` for the first smoke test.
8. Check the configured output Drive folder for generated Markdown files.

## Useful Endpoints

- `GET /api/v1/drive/status`: confirms the service account can see the input folder and write to the output folder.
- `POST /api/v1/document/batch-process`: starts Google Drive document processing in the background.
- `POST /api/v1/document/youtube-channel-process`: starts YouTube channel report generation in the background.
