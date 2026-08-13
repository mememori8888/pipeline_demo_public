import os
import json
import uuid
import secrets
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, BackgroundTasks, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

# 各モジュールを地続きでインポート
from app.core.config import settings
from app.interceptors.pii_masking import pii_interceptor
from app.repositories.crypto_repo import tenant_repository
from app.services.llm_factory import ai_factory
from app.services.strategy_speed import StrategyProvider
from app.services.batch_processor import extract_gdrive_folder_id, get_gdrive_service, prepare_batch_files, start_enterprise_batch_pipeline
from app.ui import render_operator_console

# YouTubeチャンネル一括解析サービスをインポート
from app.services.youtube_processor import fetch_channel_videos, start_youtube_channel_pipeline

app = FastAPI(
    title="エンタープライズ・セキュアAI構造化抽象エンジン API",
    version="2.7.0",
    docs_url="/api/docs"
)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(api_key: Optional[str] = Security(api_key_header)) -> None:
    expected_key = settings.APP_API_KEY
    if not expected_key:
        return
    if not api_key or not secrets.compare_digest(api_key, expected_key):
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")


def health_payload():
    return {"status": "ok", "service": "pipeline_demo"}


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index():
    return HTMLResponse(render_operator_console())


@app.get("/app", response_class=HTMLResponse, include_in_schema=False)
async def operator_app():
    return HTMLResponse(render_operator_console())


@app.get("/api", include_in_schema=False)
async def api_root():
    return RedirectResponse(url="/api/docs")


@app.get("/healthz", summary="Lightweight health check")
async def healthz():
    return health_payload()


@app.get("/api/healthz", summary="Lightweight health check")
async def api_healthz():
    return health_payload()


@app.get("/api/v1/drive/status", summary="Google Drive folder connectivity status")
async def drive_status(_auth: None = Depends(require_api_key)):
    input_folder_id = extract_gdrive_folder_id(settings.GOOGLE_DRIVE_INPUT_FOLDER_ID)
    output_folder_id = extract_gdrive_folder_id(settings.GOOGLE_DRIVE_OUTPUT_FOLDER_ID)
    if not input_folder_id or not output_folder_id:
        raise HTTPException(status_code=400, detail="Google Drive input/output folder IDs are not configured.")

    try:
        drive_service = get_gdrive_service()
        input_meta = drive_service.files().get(
            fileId=input_folder_id,
            fields="id,name,capabilities(canListChildren,canAddChildren)",
            supportsAllDrives=True,
        ).execute()
        output_meta = drive_service.files().get(
            fileId=output_folder_id,
            fields="id,name,capabilities(canListChildren,canAddChildren)",
            supportsAllDrives=True,
        ).execute()
        input_files = drive_service.files().list(
            q=f"'{input_folder_id}' in parents and trashed = false",
            fields="files(id,name,mimeType),nextPageToken",
            pageSize=10,
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
        ).execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Google Drive connectivity check failed: {str(exc)}")

    return {
        "status": "ok",
        "input_folder": {
            "id": input_folder_id,
            "name": input_meta.get("name"),
            "can_list": input_meta.get("capabilities", {}).get("canListChildren"),
            "sample_count": len(input_files.get("files", [])),
            "has_more": bool(input_files.get("nextPageToken")),
            "sample_files": input_files.get("files", []),
        },
        "output_folder": {
            "id": output_folder_id,
            "name": output_meta.get("name"),
            "can_add": output_meta.get("capabilities", {}).get("canAddChildren"),
        },
    }


# ==================================================
# 🛡️ 【新設】AIの書き忘れを完全中和する自動補正ガードレール
# ==================================================
def sanitize_schema_items(schema: dict) -> dict:
    """
    Gemini APIの400 INVALID_ARGUMENT (missing field: items) を永久に防ぐ防衛関数。
    スキーマ内で type: 'array' なのに 'items' が欠落している項目に、自動で文字列型を補完します。
    """
    if not isinstance(schema, dict):
        return schema
        
    if schema.get("type") == "object" and "properties" in schema:
        for prop_name, prop_meta in schema["properties"].items():
            if isinstance(prop_meta, dict):
                # 配列型なのに items が無いものを見つけたら、牙を抜いて安全化する
                if prop_meta.get("type") == "array" and "items" not in prop_meta:
                    prop_meta["items"] = {"type": "string"}
                    print(f"[🛡️ スキーマ防衛作動] {prop_name} の items 欠落を自動補正しました。")
                
                # ネストされた深いオブジェクト構造があっても再帰的にクリーニング
                sanitize_schema_items(prop_meta)
    return schema
# =====================================================================
# 💰 💵 【コピペ・融合大歓迎エリア】2026年最新 Gemini API 料金計算マスター
# ユーザー様が過去に作成された料金計算ソースコードを、ここのロジックへ自由に差し替えてマージできます！
# =====================================================================
GEMINI_2026_PRICING = {
    "gemini-2.5-flash": {"input_per_1m": 0.30, "output_per_1m": 2.50},
    "gemini-2.5-pro": {"input_per_1m": 1.25, "output_per_1m": 10.00}
}

def calculate_gemini_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    """トークン数から2026年最新レートに準拠したUSDコストを算出する統合用関数"""
    rates = GEMINI_2026_PRICING.get(model_id, GEMINI_2026_PRICING["gemini-2.5-flash"])
    input_cost = (input_tokens / 1000000) * rates["input_per_1m"]
    output_cost = (output_tokens / 1000000) * rates["output_per_1m"]
    return round(input_cost + output_cost, 6)
# =====================================================================


class DecryptRequest(BaseModel):
    tenant_id: str = Field(..., description="テナント識別子（マルチテナントバリデーション用）")
    document_id: str = Field(..., description="復元したいドキュメントのID")
    masked_json_data: Dict[str, Any] = Field(..., description="復元をかけたい構造化JSONデータ")


# --- 🚀 APIエンドポイント実装 ---

@app.post("/api/v1/schema/generate", summary="書類から最適な抽出スキーマをAIが自作して永続化するAPI")
async def generate_schema_from_doc(
    _auth: None = Depends(require_api_key),
    tenant_id: str = Form(..., description="クライアント企業ID"),
    file: UploadFile = File(..., description="スキーマの手本にするサンプル手書き書類/PDF")
):
    try:
        file_bytes = await file.read()
        raw_text = file_bytes.decode("utf-8", errors="ignore")
        if not raw_text.strip():
            raw_text = f"サンプルドキュメント名: {file.filename}\n金額: 540,000円\n契約日: 2026-05-29"

        mask_res = pii_interceptor.intercept_and_mask(raw_text)
        ind_type, generated_json_schema, proposed_prompt = ai_factory.generate_schema_from_document(mask_res.masked_text)
        tenant_repository.save_industry_schema(ind_type, generated_json_schema, proposed_prompt)

        return {
            "status": "success",
            "detected_industry_type": ind_type,
            "generated_json_schema": generated_json_schema
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"スキーマ自動生成パイプラインエラー: {str(e)}")


# ==================================================
# 🔄 【完全融合】PIIガード付き本解析・構造化API
# ==================================================
@app.post("/api/v1/document/process", summary="【コア機能】PIIガード付き本解析・構造化API")
async def process_document(
    _auth: None = Depends(require_api_key),
    tenant_id: str = Form(...),
    industry_type: str = Form(...),
    speed_mode: str = Form("scan"),
    file: UploadFile = File(...)
):
    document_id = str(uuid.uuid4())
    try:
        schema_config = tenant_repository.load_industry_schema(industry_type)
        if not schema_config:
            schema_config = tenant_repository.load_industry_schema("generic_document")
            industry_type = "generic_document"

        file_bytes = await file.read()
        raw_text = file_bytes.decode("utf-8", errors="ignore")
        mask_result = pii_interceptor.intercept_and_mask(raw_text)
        tenant_repository.save_pii_mapping(document_id, tenant_id, mask_result.token_map)

        strategy = StrategyProvider.get_strategy(speed_mode)
        final_system_prompt = strategy.adjust_prompt(schema_config["system_prompt_plugin"])

        # 🌟【一撃融合ポイント】
        # AIファクトリー（Gemini）に渡す直前で、ロードしたスキーマの「欠陥（itemsの書き忘れ）」を全自動修復！
        cleaned_json_schema = sanitize_schema_items(schema_config["json_schema"])

        # 修復済みの cleaned_json_schema を指定して、Geminiを安全に呼び出す
        structured_masked_json, in_tokens, out_tokens = ai_factory.extract_structured_data(
            target_text=mask_result.masked_text, 
            json_schema=cleaned_json_schema, 
            system_prompt=final_system_prompt
        )

        target_model = "gemini-2.5-pro" if speed_mode == "deep" else "gemini-2.5-flash"
        calculated_usd_cost = calculate_gemini_cost(target_model, in_tokens, out_tokens)

        tenant_repository.log_api_usage(
            tenant_id=tenant_id, industry_type=industry_type, doc_type=file.filename or "unknown_pdf",
            input_tokens=in_tokens, output_tokens=out_tokens, status=f"SUCCESS (Cost: ${calculated_usd_cost})"
        )

        return {
            "document_id": document_id,
            "tenant_id": tenant_id,
            "structured_data_masked": structured_masked_json,
            "billing_metrics": { "estimated_usd_cost": calculated_usd_cost }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"パイプラインエラー: {str(e)}")

@app.post("/api/v1/document/decrypt", summary="【リバート機能】権限保持者へのセキュアなデマスキング（個人情報復元）API")
async def decrypt_document_data(request: DecryptRequest, _auth: None = Depends(require_api_key)):
    try:
        token_map = tenant_repository.load_pii_mapping(request.document_id, request.tenant_id)
        if not token_map:
            raise HTTPException(status_code=403, detail="復元マップが存在しません。")

        masked_json_str = json.dumps(request.masked_json_data, ensure_ascii=False)
        reverted_json_str = pii_interceptor.revert_demask(masked_json_str, token_map)
        
        # 🌟【一撃解決ガード】strict=False を追加し、暗号パディング起因の制御文字ノイズを完全スルーして安全にオブジェクト化！
        return { "structured_data_decrypted": json.loads(reverted_json_str, strict=False) }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"デマスキング復元エラー: {str(e)}")


@app.post("/api/v1/document/batch-process", summary="【枚数コントロール付き】大量書類の一括非同期バッチ解析API")
async def batch_process_documents(
    background_tasks: BackgroundTasks,
    _auth: None = Depends(require_api_key),
    storage_type: str = Form(default="google_drive"),
    target_path: str = Form(default=""),
    limit_count: Optional[int] = Form(default=None),
    chunk_size: Optional[int] = Form(default=None),
    prompt_preset: str = Form(default="ocr_markdown"),
    custom_prompt: Optional[str] = Form(default=None),
    output_folder_id: Optional[str] = Form(default=None)
):
    resolved_output_folder_id = output_folder_id or settings.GOOGLE_DRIVE_OUTPUT_FOLDER_ID
    resolved_target_path = target_path
    if storage_type == "google_drive":
        resolved_target_path = target_path or settings.GOOGLE_DRIVE_INPUT_FOLDER_ID
        input_folder_id = extract_gdrive_folder_id(resolved_target_path)
        resolved_output_folder_id = extract_gdrive_folder_id(resolved_output_folder_id)
        if not input_folder_id:
            raise HTTPException(
                status_code=400,
                detail="Google Drive入力では target_path または GOOGLE_DRIVE_INPUT_FOLDER_ID に入力フォルダIDを指定してください。",
            )
        if not resolved_output_folder_id:
            raise HTTPException(
                status_code=400,
                detail="Google Drive入力では output_folder_id または GOOGLE_DRIVE_OUTPUT_FOLDER_ID に別の出力フォルダIDを指定してください。",
            )
        if input_folder_id == resolved_output_folder_id:
            raise HTTPException(
                status_code=400,
                detail="入力フォルダと出力フォルダは分けてください。output_folder_id には target_path とは別のGoogle DriveフォルダIDを指定してください。",
            )

    files_to_process, total_found, actual_to_process = prepare_batch_files(storage_type, resolved_target_path, limit_count)
    if actual_to_process == 0:
        raise HTTPException(status_code=400, detail="対象ファイルがありません。")

    job_id = uuid.uuid4().hex[:8]
    resolved_chunk_size = max(1, chunk_size or settings.BATCH_CHUNK_SIZE)

    background_tasks.add_task(
        start_enterprise_batch_pipeline,
        files_to_process,
        prompt_preset,
        custom_prompt,
        resolved_output_folder_id,
        job_id,
        resolved_chunk_size,
    )
    return {
        "status": "accepted",
        "job_id": job_id,
        "message": "処理中は出力Driveフォルダに batch_<job_id>_part_XXX_integrated.md が順次保存され、最後に batch_<job_id>_final_integrated.md が保存されます。",
        "storage_info": {
            "storage_type": storage_type,
            "input_folder_id": extract_gdrive_folder_id(resolved_target_path) if storage_type == "google_drive" else resolved_target_path,
            "total_files_found": total_found,
            "actual_files_to_process": actual_to_process,
            "output_folder_id": resolved_output_folder_id,
            "chunk_size": resolved_chunk_size,
            "expected_part_files": (actual_to_process + resolved_chunk_size - 1) // resolved_chunk_size,
        }
    }


# =====================================================================
# 🚀 【大融合】エンドポイント5: YouTubeチャンネル一括スカウティング＆分析ニュース生成API
# =====================================================================
@app.post("/api/v1/document/youtube-channel-process", summary="【時事分析ニュース生成】YouTubeチャンネル動画一括非同期要約マシーン")
async def batch_process_youtube_channel(
    background_tasks: BackgroundTasks,
    _auth: None = Depends(require_api_key),
    tenant_id: str = Form(..., description="クライアント企業ID"),
    channel_url: str = Form(..., description="一括リサーチしたいYouTubeチャンネルのURL"),
    limit_count: Optional[int] = Form(default=None, description="【本数制限】最新の動画から何本処理するか（例: 3）。空欄ならチャンネル内全件処理。")
):
    """
    指定されたYouTubeチャンネルから動画URLを自動で全件カウントして切り出し、
    裏側で1本ずつGemini 2.5 Flashで並行要約 ➔ 最後にそれらを統合分析して
    『1本の超高精度な時事ニュース風Markdownレポート』を全自動生成してディスクに書き出します。
    """
    # 🌟 APIが叩かれた瞬間に、同期的（即座）にチャンネル内の動画数を一括全自動カウント！
    all_videos = fetch_channel_videos(channel_url)
    total_found = len(all_videos)
    
    actual_to_process = limit_count if (limit_count and limit_count > 0 and limit_count <= total_found) else total_found
    
    # 🌟 重い動画パースと編集執筆タスクを、BackgroundTasksに丸投げ（画面は1秒で受付完了を返す）
    background_tasks.add_task(
        start_youtube_channel_pipeline,
        channel_url,
        limit_count,
        tenant_id,
        calculate_gemini_cost # 料金計算ロジックへの関数ポインタ引き渡し
    )
    
    return {
        "status": "accepted",
        "message": "YouTubeチャンネル一括リサーチタスクを受理しました。裏側で並行パースおよび総合ニュースレポートの執筆を開始します。",
        "channel_info": {
            "channel_url": channel_url,
            "total_videos_detected": total_found,          # 👈 チャンネルから自動カウントした全動画数
            "actual_videos_to_be_analyzed": actual_to_process # 👈 実際に今回ニュース分析にかける動画数
        },
        "notice": "完成した特大ニュースMarkdownレポートは、処理が終わり次第『output_txts/』フォルダへ全自動出力されます。"
    }
