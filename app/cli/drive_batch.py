import argparse
import asyncio
import json
import sys
import uuid
from typing import Optional

from app.core.config import settings
from app.services.batch_processor import (
    extract_gdrive_folder_id,
    prepare_batch_files,
    start_enterprise_batch_pipeline,
)


def _positive_or_none(value: Optional[int]) -> Optional[int]:
    if value is None or value <= 0:
        return None
    return value


def _compact_result(result: dict) -> dict:
    part_outputs = result.get("part_outputs") or []
    compact = {
        key: value
        for key, value in result.items()
        if key not in {"part_outputs"}
    }
    compact["part_count"] = len(part_outputs)
    compact["part_files"] = [
        {
            "index": part.get("index"),
            "file_name": part.get("file_name"),
            "gdrive_output": part.get("gdrive_output"),
        }
        for part in part_outputs
    ]
    return compact


async def _run(args: argparse.Namespace) -> int:
    target_path = args.target_path or settings.GOOGLE_DRIVE_INPUT_FOLDER_ID
    output_folder_id = args.output_folder_id or settings.GOOGLE_DRIVE_OUTPUT_FOLDER_ID
    resolved_target_path = extract_gdrive_folder_id(target_path)
    resolved_output_folder_id = extract_gdrive_folder_id(output_folder_id)

    if not resolved_target_path:
        raise ValueError("Google Drive input folder is required")
    if not resolved_output_folder_id:
        raise ValueError("Google Drive output folder is required")
    if resolved_target_path == resolved_output_folder_id:
        raise ValueError("Input and output Google Drive folders must be different")

    files_to_process, total_found, actual_to_process = prepare_batch_files(
        "google_drive",
        resolved_target_path,
        _positive_or_none(args.limit_count),
    )
    if actual_to_process == 0:
        raise ValueError("No supported files were found in the input folder")

    job_id = args.job_id or uuid.uuid4().hex[:8]
    chunk_size = max(1, args.chunk_size or settings.BATCH_CHUNK_SIZE)
    print(
        json.dumps(
            {
                "status": "starting",
                "job_id": job_id,
                "storage_type": "google_drive",
                "input_folder_id": resolved_target_path,
                "output_folder_id": resolved_output_folder_id,
                "total_files_found": total_found,
                "actual_files_to_process": actual_to_process,
                "chunk_size": chunk_size,
            },
            ensure_ascii=False,
        )
    )

    result = await start_enterprise_batch_pipeline(
        files_to_process=files_to_process,
        prompt_preset=args.prompt_preset,
        custom_prompt=args.custom_prompt,
        output_folder_id=resolved_output_folder_id,
        job_id=job_id,
        chunk_size=chunk_size,
    )
    print(json.dumps(_compact_result(result), ensure_ascii=False, default=str))
    return 0 if result.get("status") == "DONE" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Google Drive batch pipeline once.")
    parser.add_argument("--target-path", default="", help="Google Drive input folder ID or URL")
    parser.add_argument("--output-folder-id", default="", help="Google Drive output folder ID or URL")
    parser.add_argument("--limit-count", type=int, default=0, help="0 means all supported files")
    parser.add_argument("--chunk-size", type=int, default=0, help="0 means the configured default")
    parser.add_argument("--prompt-preset", default="ocr_markdown")
    parser.add_argument("--custom-prompt", default=None)
    parser.add_argument("--job-id", default="")
    args = parser.parse_args()

    try:
        return asyncio.run(_run(args))
    except Exception as err:
        print(json.dumps({"status": "failed", "error": str(err)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
