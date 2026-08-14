# Long Batch Follow-up - 2026-08-14

## Current Result

Cloud Run job `7bf45fe0` processed the input Drive folder through:

- `batch_7bf45fe0_part_001_integrated.md`
- `batch_7bf45fe0_part_002_integrated.md`
- `batch_7bf45fe0_part_003_integrated.md`
- `batch_7bf45fe0_part_004_integrated.md`
- `batch_7bf45fe0_part_005_integrated.md`
- `batch_7bf45fe0_part_006_integrated.md`
- `batch_7bf45fe0_part_007_integrated.md`
- `batch_7bf45fe0_part_008_integrated.md`
- `batch_7bf45fe0_part_009_integrated.md`

It did not create `batch_7bf45fe0_final_integrated.md`, so that run did not become one complete book.

## Cause

The original FastAPI endpoint returned `accepted` immediately and continued the Gemini/Drive processing as an HTTP background task.

That is not reliable for a full-folder batch on Cloud Run. After the HTTP response finishes, Cloud Run can stop or replace the instance, so long background work may stop before the final integration step.

## Fix

- Added `app.cli.drive_batch`, a one-shot entrypoint for Cloud Run Jobs.
- Updated `POST /api/v1/document/batch-process` so it can start a Cloud Run Job when `CLOUD_RUN_BATCH_JOB_NAME` is configured.
- Kept the old FastAPI background path as a fallback for environments where no Cloud Run Job is configured.
- Added `BATCH_KEEP_PART_FILES=false` default behavior. After the final integrated Markdown is saved, temporary `part_XXX` files are moved to Google Drive trash.

## Expected Output After the Fix

For a full successful run, the output Drive folder should contain the final book:

- `<document-title>_<job_id>.md`

The title is derived from the first top-level Markdown heading generated in the final integrated document. If a usable title cannot be found, the fallback name is `integrated_book_<job_id>.md`.

Temporary files:

- `batch_<job_id>_part_001_integrated.md`
- `batch_<job_id>_part_002_integrated.md`
- ...

are only used as intermediate material and are moved to Drive trash after the final file is created.
