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
from google.genai import errors
from app.core.config import settings

# Google公式 API クライアントライブラリ
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from google.oauth2 import service_account

# Gemini API クライアントの初期化
client = genai.Client(api_key=settings.GEMINI_API_KEY)

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
SEMAPHORE_LIMIT = 3
semaphore = asyncio.Semaphore(SEMAPHORE_LIMIT)

async def upload_and_process_with_retry(file: FilePayload, system_prompt: str, drive_service=None) -> str:
    async with semaphore:
        print(f"[⚙️ 各頁スキャン中...]: {file.file_name}")
        try:
            if file.gdrive_file_id:
                if not drive_service:
                    drive_service = get_gdrive_service()
                request = drive_service.files().get_media(fileId=file.gdrive_file_id)
                file_stream = io.BytesIO()
                downloader = MediaIoBaseDownload(file_stream, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
                file_bytes = file_stream.getvalue()
            else:
                with open(file.local_path, "rb") as f:
                    file_bytes = f.read()

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

            max_retries = 3
            base_delay = 2
            response = None
            
            for attempt in range(max_retries):
                try:
                    response = client.models.generate_content(model=settings.DEFAULT_MODEL_ID, contents=contents_input)
                    break
                except Exception as g_err:
                    err_msg = str(g_err)
                    is_temporary = "503" in err_msg or "429" in err_msg or "UNAVAILABLE" in err_msg or "demand" in err_msg
                    if is_temporary and attempt < max_retries - 1:
                        sleep_time = base_delay * (attempt + 1)
                        print(f"[⏳ Google混雑検知]: 『{file.file_name}』で混雑を検知。{sleep_time}秒後に自動リトライします... ({attempt + 1}/{max_retries})")
                        await asyncio.sleep(sleep_time)
                    else:
                        raise g_err

            # 🌟 後から見返せるよう、MIMEタイプ等も記載した綺麗なぶつ切りレポート素材を作成
            return (
                f"### 📄 画像カルテ: {file.file_name}\n"
                f"- **Google Drive File ID**: `{file.gdrive_file_id if file.gdrive_file_id else 'N/A'}`\n"
                f"- **検知MIMEタイプ**: `{file.mime_type}`\n"
                f"- **抽出ログ本文**:\n"
                f"{response.text}\n\n"
                f"--- \n\n"
            )

        except Exception as api_err:
            print(f"[❌ 解析断念] {file.file_name} エラー: {str(api_err)}")
            return f"### ❌ 解析失敗ページ: {file.file_name}\n- **理由**: {str(api_err)}\n\n--- \n\n"


# ==================================================
# 🚀 4. メイン非同期パイプライン（本編 ＋ ぶつ切り付録完全合体版）
# ==================================================
async def start_enterprise_batch_pipeline(
    files_to_process: List[FilePayload],
    prompt_preset: str,
    custom_prompt: Optional[str] = None,
    output_folder_id: Optional[str] = None,
    **kwargs
) -> dict:
    start_time = time.time()
    tenant_id = "geoai-production"

    # フェーズ1用の下読み指示
    phase1_prompt = "渡された書類（画像）の文字、図表、意味を極めて詳細に文字起こしし、データ要素を過不足なく抽出して日本語で報告してください。"

    if not files_to_process:
        print("[❌ 終了] バックグラウンドに渡されたファイルリストが空でした。")
        return {"status": "EMPTY"}

    is_gdrive = any(f.gdrive_file_id for f in files_to_process)
    drive_service = get_gdrive_service() if is_gdrive else None

    # --------------------------------------------------
    # 🌟 【フェーズ 1】各個撃破（全画像の詳細な下読み ➔ ぶつ切りレポートの生成）
    # --------------------------------------------------
    print(f"[🚀 フェーズ1起動] 画像 {len(files_to_process)} 枚の並行下読みを開始します。")
    tasks = [upload_and_process_with_retry(f, phase1_prompt, drive_service) for f in files_to_process]
    intermediate_results = await asyncio.gather(*tasks)
    
    # 10枚分の「ぶつ切りレポート」をすべて合体させた巨大なデータプール
    all_pages_context = "".join(intermediate_results)
    
    # --------------------------------------------------
    # 🌟 【フェーズ 2】統合シンキング（一気読みして「本」に再構築）
    # --------------------------------------------------
    print("\n[🧠 フェーズ2：統合シンキング起動] 全ての下読みデータを回収しました。一冊の本として、もう一度熟読・再構成しています...")
    
    if custom_prompt:
        synthesis_prompt = custom_prompt
    else:
        synthesis_prompt = (
            "# 📚 書籍化・統合編集最高命令\n"
            "高度な知識書籍の編集長、兼シニアAIエグゼクティブアナリストとして振る舞ってください。\n"
            "以下に渡される「全ページ分の個別下読みデータ」のすべてを熟読・咀嚼してください。\n"
            "全体のデータから浮かび上がる背景、共通するトレンド、本質的な知識を紡ぎ出し、"
            "流れるような1本のシームレスな『完成された書籍（またはインテリジェンス白書）』としてMarkdown形式で大脱皮させてください。\n\n"
            "## 📖 本の構成案:\n"
            "1. **本のタイトル**: 収集された情報全体を象徴する、知的大ヒットを予感させる美しいタイトル（# タイトル）\n"
            "2. **プロローグ（はじめに）**: この書籍（書類群）全体が扱っているテーマ、その背景と意義（## はじめに）\n"
            "3. **核心的総括**: 全ページを横断して見えてきた、核心的な重要キーワードや共通するトレンド、重要な数字の統合まとめ（## 核心的総括）\n"
            "4. **体系的な本文（章立て）**: 下読みデータを論理的に構造化し、流れるような文脈で整理した各論（## 各論：体系的分析）\n"
            "5. **エピローグ（結びにかえて）**: 全体のデータを統合した結論、および未来への展望・総括（## 結論と今後の展望）\n\n"
            "## 🎨 文体・執筆ルール:\n"
            "- 完全に「である調（常体）」で統一し、学術書や高級ビジネス書としての品格を保つこと。\n"
            "- 「解析しました」などのシステム的な前置きは一切禁止。そのまま出版できるクオリティにすること。"
        )

    # Geminiに全データを渡して「2回目の超シンキング」
    final_synthesis_response = client.models.generate_content(
        model=settings.DEFAULT_MODEL_ID,
        contents=[
            f"■ 全ページ分の個別下読みデータ（素材）:\n\n{all_pages_context}",
            synthesis_prompt
        ]
    )
    
    final_book_markdown = final_synthesis_response.text

    # --------------------------------------------------
    # 🌟 【合体フェーズ】本編の後ろに「ぶつ切りレポート一覧」を完全ドッキング！
    # --------------------------------------------------
    complete_report_markdown = (
        f"{final_book_markdown}\n\n"
        f" \n\n"
        f"# 📁 📘 付録（Appendix）：各ページの一次詳細解析データ一覧\n"
        f"--- \n"
        f"上記の『統合白書（本編）』を執筆するにあたり、AIエンジンが1枚1枚の画像データから"
        f"事前にディープスキャンして抽出した、元データおよび証拠（エビデンス）の全記録です。検証用の生データとしてご活用ください。\n\n"
        f"{all_pages_context}"
    )

    # --------------------------------------------------
    # 💾 成果物の物理出荷（ローカル本棚保存）
    # --------------------------------------------------
    file_name = f"integrated_book_analysis_{uuid.uuid4().hex[:8]}.md"
    file_path = os.path.join(OUTPUT_DIR, file_name)
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(complete_report_markdown)

    gdrive_result = None
    resolved_output_folder_id = extract_gdrive_folder_id(output_folder_id or settings.GOOGLE_DRIVE_OUTPUT_FOLDER_ID)
    if resolved_output_folder_id:
        gdrive_result = upload_markdown_to_gdrive(
            file_name=file_name,
            content=complete_report_markdown,
            folder_id=resolved_output_folder_id,
            drive_service=drive_service,
        )
        
    elapsed = time.time() - start_time
    print(f"\n[🎉 バッチ完全終了] 処理時間: {elapsed:.2f}秒")
    print(f"[📂 保存先パス]: {file_path}")
    print("成果物は『本編 ＋ ぶつ切り生データ付録』が合体した状態でローカル本棚に出荷されました！")
    
    if gdrive_result:
        print(f"[Google Drive output]: {gdrive_result}")

    return {
        "destination": file_path,
        "gdrive_output": gdrive_result,
        "processed_count": len(files_to_process),
    }


def prepare_batch_files(storage_type: str, target_path: str, limit_count: Optional[int] = None) -> Tuple[List[FilePayload], int, int]:
    payloads = scan_storage(storage_type, target_path, limit_count)
    total_found = len(payloads)
    actual_to_process = len(payloads)
    return payloads, total_found, actual_to_process
