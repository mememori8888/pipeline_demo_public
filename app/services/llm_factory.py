import json
from typing import Dict, Any, Tuple
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from app.core.config import settings

# --- フールプルーフのためのスキーマ生成用Pydantic定義 ---
class SchemaProperty(BaseModel):
    key_name: str = Field(description="抽出する項目の英名（例: total_amount, patient_name）")
    type_str: str = Field(description="データの型。string, number, boolean, array のいずれか")
    description: str = Field(description="この項目が何を意味するか、日本語での詳細な説明。LLMへの指示になります。")

class GeneratedSchemaPayload(BaseModel):
    industry_type_recommended: str = Field(description="書類から推測される最適な業界・書類識別名（例: medical_invoice, real_estate_contract）")
    proposed_system_prompt: str = Field(description="この種類の書類を解析する際に、AIに与えるべき専門家としてのシステムプロンプト指示文")
    properties_to_extract: list[SchemaProperty] = Field(description="この書類から抽出を推奨する主要なデータ項目のリスト")


class GeminiSaaSFactory:
    """Gemini 2.5の最新機能をマルチテナント向けにカプセル化したAIファクトリー"""

    def __init__(self):
        # 最新SDKクライアント初期化
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_id = settings.DEFAULT_MODEL_ID

    def generate_schema_from_document(self, masked_sample_text: str) -> Tuple[str, Dict[str, Any], str]:
        """
        ★コア要件：書類（マスキング済みテキスト）を解析し、
        AI自身に最適なJSON Schemaとシステムプロンプトを『自作』させる機能
        """
        prompt = f"""
        あなたは超一流のデータアーキテクトです。提供された以下のドキュメント（個人情報マスキング済み）の内容と構造を深く分析してください。
        この種類のドキュメントから「どの項目を抽出すれば業務効率化・SaaS化において最も価値が出るか」を熟考し、
        最適なデータ抽出用スキーマ、専門的なシステムプロンプト、および推奨される業界識別名を設計して定義してください。

        【解析対象ドキュメント】
        {masked_sample_text}
        """

        # Structured Outputsを使い、AIに正確なスキーマメタデータを吐き出させる
        response = self.client.models.generate_content(
            model=self.model_id,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=GeneratedSchemaPayload,
                temperature=0.2
            )
        )
        
        # 解析結果のパース
        result = json.loads(response.text)
        
        # AIの提案から標準的な「JSON Schema」構造をプログラム側で動的に組み立てる（フールプルーフ）
        properties_json: Dict[str, Any] = {}
        required_fields = []
        
        for prop in result["properties_to_extract"]:
            properties_json[prop["key_name"]] = {
                "type": prop["type_str"],
                "description": prop["description"]
            }
            required_fields.append(prop["key_name"])
            
        final_json_schema = {
            "type": "object",
            "properties": properties_json,
            "required": required_fields
        }
        
        return result["industry_type_recommended"], final_json_schema, result["proposed_system_prompt"]

    def extract_structured_data(self, target_text: str, json_schema: Dict[str, Any], system_prompt: str) -> Tuple[Dict[str, Any], int, int]:
        """動的なJSON SchemaをGeminiに注入し、厳格に型保証された構造化データを抜き出す"""
        
        # 動的スキーマオブジェクトを直接GenerateContentConfigにバイパス
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=json_schema,  # 動的な辞書型スキーマを直接受容
            temperature=0.1
        )
        
        response = self.client.models.generate_content(
            model=self.model_id,
            contents=target_text,
            config=config
        )
        
        # トークン消費量の取得（マネタイズ用。SDKのメタデータからフェイルセーフに取得）
        input_tokens = response.usage_metadata.prompt_token_count if response.usage_metadata else 0
        output_tokens = response.usage_metadata.candidates_token_count if response.usage_metadata else 0
        
        return json.loads(response.text), input_tokens, output_tokens

ai_factory = GeminiSaaSFactory()