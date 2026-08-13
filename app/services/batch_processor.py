import os
import io
import json
import asyncio
import uuid
import time
import re
from typing import List, Optional, Tuple
from pydantic import BaseModel
import google.auth
from google import genai
from google.genai import types
from app.core.config import settings

# Google公式 API クライアントライブラリ
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from google.oauth2 import service_account

# Gemini API クライアントの初期化
client = genai.Client(
    api_key=settings.GEMINI_API_KEY,
    http_options=types.HttpOptions(timeout=settings.GEMINI_HTTP_TIMEOUT_MS),
)

# 成果物を格納するローカルの安全な本棚フォルダ
OUTPUT_DIR = "output_txts"
os.makedirs(OUTPUT_DIR, exist_ok=True)


class FilePayload(BaseModel):
    file_name: str
    local_path: Optional[str] = None
    gdrive_file_id: Optional[str] = None
    mime_type: str


# ==================================================
# 🔑 1. Google ドライブ API 認証
# ==================================================
def get_gdrive_service():
    scopes = ["https://www.googleapis.com/auth/drive"]
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "service_account.json")
    if os.path.exists(cred_path):
        creds = service_account.Credentials.from_service_account_file(cred_path, scopes=scopes)
    else:
        creds, _ = google.auth.default(scopes=scopes)
    return build('drive', 'v3', credentials=creds)


def extract_gdrive_folder_id(folder_ref: Optional[str]) -> Optional[str]:
    if not folder_ref:
        return None
    folder_ref = folder_ref.strip()
    url_match = re.search(r"folders/([a-zA-Z0-9-_]+)", folder_ref)
    if url_match:
        return url_match.group(1)
    return folder_ref


def upload_markdown_to_gdrive(file_name: str, content: str, folder_id: str, drive_service=None) -> dict:
    service = drive_service or get_gdrive_service()
    metadata = {
        "name": file_name,
        "mimeType": "text/markdown",
        "parents": [folder_id],
    }
    media = MediaIoBaseUpload(
        io.BytesIO(content.encode("utf-8")),
        mimetype="text/markdown",
        resumable=False,
    )
    created = service.files().create(
        body=metadata,
        media_body=media,
        fields="id, name, webViewLink",
        supportsAllDrives=True,
    ).execute()
    return {
        "file_id": created.get("id"),
        "file_name": created.get("name", file_name),
        "web_view_link": created.get("webViewLink"),
    }


def save_markdown_locally(file_name: str, content: str) -> str:
    file_path = os.path.join(OUTPUT_DIR, file_name)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    return file_path


def read_file_bytes(file: FilePayload) -> bytes:
    if file.gdrive_file_id:
        drive_service = get_gdrive_service()
        request = drive_service.files().get_media(fileId=file.gdrive_file_id)
        file_stream = io.BytesIO()
        downloader = MediaIoBaseDownload(file_stream, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return file_stream.getvalue()

    with open(file.local_path, "rb") as f:
        return f.read()


def chunk_payloads(files: List[FilePayload], chunk_size: int) -> List[List[FilePayload]]:
    safe_chunk_size = max(1, chunk_size)
    return [files[i:i + safe_chunk_size] for i in range(0, len(files), safe_chunk_size)]


# ==================================================
# 📂 2. ストレージ・スキャン
# ==================================================
def scan_storage(storage_type: str, target_path: str, limit_count: Optional[int] = None) -> List[FilePayload]:
    payloads = []
    
    if storage_type == "local":
        print(f"[📂 ローカルスキャン起動] 対象パス: {target_path}")
        for root, _, files in os.walk(target_path):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in ['.pdf', '.png', '.jpg', '.jpeg', '.txt', '.heic']:
                    if ext == '.pdf': mime_type = "application/pdf"
                    elif ext in ['.png', '.jpg', '.jpeg']: mime_type = "image/png"
                    elif ext == '.txt': mime_type = "text/plain"
                    elif ext == '.heic': mime_type = "image/heic"
                    payloads.append(FilePayload(file_name=file, local_path=os.path.join(root, file), mime_type=mime_type))
                    
    elif storage_type == "google_drive":
        if "drive.google.com" in target_path:
            url_match = re.search(r'folders/([a-zA-Z0-9-_]+)', target_path)
            if url_match:
                target_path = url_match.group(1)
                print(f"[🛡️ URL自動補正] フォルダID 『{target_path}』 を自動抽出しました。")

        print(f"[🌐 Google Drive本線接続] フォルダID: {target_path} をスキャン中...")
        try:
            drive_service = get_gdrive_service()
            page_token = None
            max_scan = limit_count if (limit_count and limit_count > 0) else 10000
            
            while len(payloads) < max_scan:
                query = f"'{target_path}' in parents and trashed = false"
                response = drive_service.files().list(
                    q=query, fields="nextPageToken, files(id, name, mimeType)",
                    pageSize=100,
                    pageToken=page_token,
                    includeItemsFromAllDrives=True,
                    supportsAllDrives=True,
                ).execute()
                
                for file in response.get('files', []):
                    file_name = file.get('name', '')
                    ext = os.path.splitext(file_name)[1].lower()
                    drive_mime = file.get('mimeType', '')
                    
                    supported_exts = ['.pdf', '.png', '.jpg', '.jpeg', '.txt', '.heic']
                    supported_mimes = ["application/pdf", "image/png", "image/jpeg", "image/jpg", "text/plain", "image/heic", "image/x-mac-heic"]
                    
                    if drive_mime in supported_mimes or ext in supported_exts:
                        if ext == '.pdf': mime_type = "application/pdf"
                        elif ext in ['.png', '.jpg', '.jpeg']: mime_type = "image/png"
                        elif ext == '.txt': mime_type = "text/plain"
                        elif ext == '.heic': mime_type = "image/heic"
                        else: mime_type = drive_mime
                        
                        payloads.append(FilePayload(file_name=file_name, gdrive_file_id=file['id'], mime_type=mime_type))
                        
                    if len(payloads) >= max_scan:
                        break
                page_token = response.get('nextPageToken')
                if not page_token:
                    break
        except Exception as e:
            print(f"[❌ Google ドライブ通信エラー]: {str(e)}")
            
    if limit_count and limit_count > 0:
        payloads = payloads[:limit_count]
        
    print(f"[✅ スキャン完了] 最終処理対象ファイル数: {len(payloads)} 件")
    return payloads


# ==================================================
# 🛡️ 3. 【フェーズ1：各個撃破用】多重度制限 ＆ 各頁詳細解析
# ==================================================
SEMAPHORE_LIMIT = max(1, settings.BATCH_PAGE_CONCURRENCY)
semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)
TEMPORARY_ERROR_HINTS = (
    "503",
    "429",
    "408",
    "504",
    "UNAVAILABLE",
    "demand",
    "timeout",
    "timed out",
    "ReadTimeout",
)


def is_temporary_gemini_error(err_msg: str) -> bool:
    lowered = err_msg.lower()
    return any(hint.lower() in lowered for hint in TEMPORARY_ERROR_HINTS)


async def generate_content_text_with_retry(contents_input, purpose: str, max_retries: Optional[int] = None) -> str:
    max_retries = max_retries or settings.GEMINI_MAX_RETRIES
    base_delay = settings.GEMINI_RETRY_BASE_DELAY_SECONDS
    for attempt in range(max_retries):
        try:
            print(f"[Gemini start] {purpose} ({attempt + 1}/{max_retries})")
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=settings.DEFAULT_MODEL_ID,
                contents=contents_input,
            )
            print(f"[Gemini done] {purpose}")
            return response.text
        except Exception as g_err:
            err_msg = str(g_err)
            if is_temporary_gemini_error(err_msg) and attempt < max_retries - 1:
                sleep_time = base_delay * (attempt + 1)
                print(f"[⏳ Gemini一時エラー] {purpose}: {err_msg} / {sleep_time}秒後にリトライします。")
                await asyncio.sleep(sleep_time)
                continue
            raise RuntimeError(f"{purpose} のGemini生成に失敗しました: {err_msg}") from g_err

async def upload_and_process_with_retry(file: FilePayload, system_prompt: str, drive_service=None) -> str:
    async with semaphore:
        print(f"[⚙️ 各頁スキャン中...]: {file.file_name}")
        try:
            file_bytes = await asyncio.to_thread(read_file_bytes, file)

            if len(file_bytes) == 0:
                raise ValueError("ファイルが0バイトのためスキップします。")

            if file.mime_type == "text/plain":
                content_body = file_bytes.decode("utf-8", errors="ignore")
                contents_input = f"{system_prompt}\n\n■ 対象テキスト:\n{content_body}"
            else:
                from google.genai import types
                contents_input = [
                    types.Part.from_bytes(data=file_bytes, mime_type=file.mime_type),
                    system_prompt
                ]

            response_text = await generate_content_text_with_retry(
                contents_input,
                purpose=f"page:{file.file_name}",
            )

            # 🌟 後から見返せるよう、MIMEタイプ等も記載した綺麗なぶつ切りレポート素材を作成
            return (
                f"### 📄 画像カルテ: {file.file_name}\n"
                f"- **Google Drive File ID**: `{file.gdrive_file_id if file.gdrive_file_id else 'N/A'}`\n"
                f"- **検知MIMEタイプ**: `{file.mime_type}`\n"
                f"- **抽出ログ本文**:\n"
                f"{response_text}\n\n"
                f"--- \n\n"
            )

        except Exception as api_err:
            print(f"[❌ 解析断念] {file.file_name} エラー: {str(api_err)}")
            return f"### ❌ 解析失敗ページ: {file.file_name}\n- **理由**: {str(api_err)}\n\n--- \n\n"
        finally:
            delay = max(0.0, settings.BATCH_DELAY_BETWEEN_FILES_SECONDS)
            if delay:
                print(f"[低負荷待機] 次のファイル処理まで {delay:.1f} 秒待機します。")
                await asyncio.sleep(delay)


# ==================================================
# 🚀 4. メイン非同期パイプライン（本編 ＋ ぶつ切り付録完全合体版）
# ==================================================
async def start_enterprise_batch_pipeline(
    files_to_process: List[FilePayload],
    prompt_preset: str,
    custom_prompt: Optional[str] = None,
    output_folder_id: Optional[str] = None,
    job_id: Optional[str] = None,
    chunk_size: Optional[int] = None,
    **kwargs
) -> dict:
    start_time = time.time()
    job_id = job_id or uuid.uuid4().hex[:8]
    resolved_chunk_size = max(1, chunk_size or settings.BATCH_CHUNK_SIZE)
    resolved_output_folder_id = extract_gdrive_folder_id(output_folder_id or settings.GOOGLE_DRIVE_OUTPUT_FOLDER_ID)
    drive_service = get_gdrive_service() if resolved_output_folder_id else None

    phase1_prompt = "渡された書類（画像）の文字、図表、意味を極めて詳細に文字起こしし、データ要素を過不足なく抽出して日本語で報告してください。"

    base_integration_prompt = custom_prompt or (
        "# 書籍化・統合編集最高命令\n"
        "高度な知識書籍の編集長、兼シニアAIエグゼクティブアナリストとして振る舞ってください。\n"
        "渡された個別下読みデータのすべてを熟読し、要点の羅列や短いサマリーではなく、"
        "流れるような1本の統合されたMarkdown原稿として再構成してください。\n\n"
        "## 構成\n"
        "1. 本のタイトル\n"
        "2. はじめに\n"
        "3. 核心的総括\n"
        "4. 体系的な本文\n"
        "5. 結論と今後の展望\n\n"
        "## 文体\n"
        "- 完全に「である調」で統一すること。\n"
        "- システム的な前置きは書かず、そのまま読める原稿にすること。"
    )

    async def synthesize_markdown(source_context: str, prompt: str) -> str:
        return await generate_content_text_with_retry(
            [
                f"■ 統合対象データ:\n\n{source_context}",
                prompt,
            ],
            purpose="integration",
        )

    async def integrate_units(units: List[str], final_prompt: str) -> str:
        current_units = units
        round_number = 1

        while len("\n\n".join(current_units)) > settings.BATCH_SYNTHESIS_MAX_CHARS and len(current_units) > 1:
            next_units = []
            for group_index, start_index in enumerate(range(0, len(current_units), 3), start=1):
                end_index = min(start_index + 3, len(current_units))
                grouped_context = "\n\n".join(current_units[start_index:end_index])
                intermediate_prompt = (
                    f"{base_integration_prompt}\n\n"
                    f"これは最終統合前の中間統合ラウンド {round_number} / グループ {group_index} です。"
                    "短いサマリーではなく、この範囲の分割統合原稿をさらに1本の統合原稿へ編集してください。"
                )
                next_units.append(await synthesize_markdown(grouped_context, intermediate_prompt))
            current_units = next_units
            round_number += 1

        return await synthesize_markdown("\n\n".join(current_units), final_prompt)

    if not files_to_process:
        print("[❌ 終了] バックグラウンドに渡されたファイルリストが空でした。")
        return {"status": "EMPTY", "job_id": job_id}

    part_outputs = []

    try:
        chunks = chunk_payloads(files_to_process, resolved_chunk_size)
        total_chunks = len(chunks)
        print(f"[🚀 バッチ起動] job_id={job_id} / 対象 {len(files_to_process)} 件 / {resolved_chunk_size}件ずつ {total_chunks} 分割で処理します。")

        for chunk_index, chunk_files in enumerate(chunks, start=1):
            print(f"[📦 分割 {chunk_index}/{total_chunks}] {len(chunk_files)} 件の下読みを開始します。")
            tasks = [upload_and_process_with_retry(f, phase1_prompt) for f in chunk_files]
            chunk_results = await asyncio.gather(*tasks)
            chunk_context = "".join(chunk_results)
            file_list = "\n".join(f"- {f.file_name}" for f in chunk_files)

            part_prompt = (
                f"{base_integration_prompt}\n\n"
                f"これは全体 {total_chunks} 分割のうち {chunk_index} 番目の分割データです。"
                "短いサマリーではなく、この分割範囲を読み物として成立する統合原稿にしてください。"
                "後工程でこの分割統合原稿をさらに全体統合するため、重要な固有名詞、数値、論理関係を落とさないでください。"
            )
            part_integrated_markdown = await synthesize_markdown(chunk_context, part_prompt)
            part_file_name = f"batch_{job_id}_part_{chunk_index:03d}_integrated.md"
            part_document = (
                f"# Batch {job_id} Part {chunk_index:03d}/{total_chunks:03d}\n\n"
                f"## 対象ファイル\n\n{file_list}\n\n"
                f"## 分割統合原稿\n\n{part_integrated_markdown}\n\n"
                f"## 一次詳細解析データ\n\n{chunk_context}"
            )
            part_file_path = save_markdown_locally(part_file_name, part_document)
            part_gdrive_result = None
            if resolved_output_folder_id:
                part_gdrive_result = upload_markdown_to_gdrive(
                    file_name=part_file_name,
                    content=part_document,
                    folder_id=resolved_output_folder_id,
                    drive_service=drive_service,
                )
            part_outputs.append({
                "index": chunk_index,
                "file_name": part_file_name,
                "file_path": part_file_path,
                "gdrive_output": part_gdrive_result,
                "integrated_markdown": part_integrated_markdown,
            })
            print(f"[✅ 分割出力完了] {part_file_name}")
            if part_gdrive_result:
                print(f"[Google Drive part output]: {part_gdrive_result}")
            chunk_delay = max(0.0, settings.BATCH_DELAY_BETWEEN_CHUNKS_SECONDS)
            if chunk_delay and chunk_index < total_chunks:
                print(f"[低負荷待機] 次の分割処理まで {chunk_delay:.1f} 秒待機します。")
                await asyncio.sleep(chunk_delay)

        print("[🧠 最終統合] 分割統合ファイル群を1本の完成原稿へ統合します。")
        part_sources = [
            f"## 分割統合ファイル {part['index']:03d}: {part['file_name']}\n\n{part['integrated_markdown']}"
            for part in part_outputs
        ]
        final_prompt = (
            f"{base_integration_prompt}\n\n"
            "ここに渡される素材は、個別画像から作った分割統合原稿群です。"
            "これらを単に要約せず、重複を整理し、章立てと論理の流れを整え、"
            "1本の完成された統合Markdown原稿として再編集してください。"
            "分割番号や処理都合は本文に残さず、自然な最終文書にしてください。"
        )
        final_book_markdown = await integrate_units(part_sources, final_prompt)

        part_links = "\n".join(
            f"- [{part['file_name']}]({part['gdrive_output'].get('web_view_link')})"
            if part["gdrive_output"] and part["gdrive_output"].get("web_view_link")
            else f"- {part['file_name']}"
            for part in part_outputs
        )
        final_file_name = f"batch_{job_id}_final_integrated.md"
        final_document = (
            f"{final_book_markdown}\n\n"
            f"---\n\n"
            f"# 分割統合ファイル一覧\n\n"
            f"{part_links}\n"
        )
        final_file_path = save_markdown_locally(final_file_name, final_document)

        final_gdrive_result = None
        if resolved_output_folder_id:
            final_gdrive_result = upload_markdown_to_gdrive(
                file_name=final_file_name,
                content=final_document,
                folder_id=resolved_output_folder_id,
                drive_service=drive_service,
            )

        elapsed = time.time() - start_time
        print(f"\n[🎉 バッチ完全終了] job_id={job_id} / 処理時間: {elapsed:.2f}秒")
        print(f"[📂 最終保存先パス]: {final_file_path}")
        if final_gdrive_result:
            print(f"[Google Drive final output]: {final_gdrive_result}")

        return {
            "status": "DONE",
            "job_id": job_id,
            "destination": final_file_path,
            "gdrive_output": final_gdrive_result,
            "part_outputs": part_outputs,
            "processed_count": len(files_to_process),
        }
    except Exception as pipeline_err:
        elapsed = time.time() - start_time
        error_file_name = f"batch_{job_id}_error.md"
        completed_parts = "\n".join(f"- {part['file_name']}" for part in part_outputs) or "- なし"
        error_document = (
            f"# Batch {job_id} Error Report\n\n"
            f"- 処理件数: {len(files_to_process)}\n"
            f"- 完了済み分割ファイル:\n{completed_parts}\n"
            f"- 経過秒数: {elapsed:.2f}\n\n"
            f"## エラー\n\n```text\n{str(pipeline_err)}\n```\n"
        )
        error_file_path = save_markdown_locally(error_file_name, error_document)
        error_gdrive_result = None
        if resolved_output_folder_id:
            error_gdrive_result = upload_markdown_to_gdrive(
                file_name=error_file_name,
                content=error_document,
                folder_id=resolved_output_folder_id,
                drive_service=drive_service,
            )
        print(f"[❌ バッチ異常終了] job_id={job_id}: {str(pipeline_err)}")
        if error_gdrive_result:
            print(f"[Google Drive error output]: {error_gdrive_result}")
        return {
            "status": "ERROR",
            "job_id": job_id,
            "destination": error_file_path,
            "gdrive_output": error_gdrive_result,
            "processed_count": len(files_to_process),
        }


def prepare_batch_files(storage_type: str, target_path: str, limit_count: Optional[int] = None) -> Tuple[List[FilePayload], int, int]:
    payloads = scan_storage(storage_type, target_path, limit_count)
    total_found = len(payloads)
    actual_to_process = len(payloads)
    return payloads, total_found, actual_to_process
