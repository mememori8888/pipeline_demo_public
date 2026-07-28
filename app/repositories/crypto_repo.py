import json
import uuid
from typing import Dict, Any, Optional, List
from app.database.connection import get_sqlite_conn
from app.core.security import crypto_engine

class SharedTenantRepository:
    """マルチテナント対応の暗号化データ・ログ永続化レポジトリ"""

    def save_pii_mapping(self, document_id: str, tenant_id: str, token_map: Dict[str, str]) -> None:
        """個人情報の復元マップを暗号化してSQLiteに保存（フェイルセーフ）"""
        if not token_map:
            return
        with get_sqlite_conn() as conn:
            cursor = conn.cursor()
            for token, raw_value in token_map.items():
                encrypted_val = crypto_engine.encrypt(raw_value)
                cursor.execute("""
                    INSERT INTO pii_maps (document_id, tenant_id, masked_token, encrypted_original_value)
                    VALUES (?, ?, ?, ?)
                """, (document_id, tenant_id, token, encrypted_val))
            conn.commit()

    def load_pii_mapping(self, document_id: str, tenant_id: str) -> Dict[str, str]:
        """指定されたドキュメントの復元マップを安全に復号してロード"""
        token_map: Dict[str, str] = {}
        with get_sqlite_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT masked_token, encrypted_original_value FROM pii_maps
                WHERE document_id = ? AND tenant_id = ?
            """, (document_id, tenant_id))
            rows = cursor.fetchall()
            for row in rows:
                decrypted_val = crypto_engine.decrypt(row["encrypted_original_value"])
                token_map[row["masked_token"]] = decrypted_val
        return token_map

    def save_industry_schema(self, industry_type: str, json_schema_dict: Dict[str, Any], system_prompt: str) -> None:
        """AIが自動生成したスキーマとプロンプトを保存・更新（修正版）"""
        with get_sqlite_conn() as conn:
            cursor = conn.cursor()
            # json_schema_dict（辞書型）を json.dumps() で文字列化してSQLiteへ渡す
            cursor.execute("""
                INSERT OR REPLACE INTO industry_schemas (industry_type, json_schema, system_prompt_plugin)
                VALUES (?, ?, ?)
            """, (industry_type, json.dumps(json_schema_dict), system_prompt))
            conn.commit()

    def load_industry_schema(self, industry_type: str) -> Optional[Dict[str, Any]]:
        """データベースから業界別スキーマ設定をロード"""
        with get_sqlite_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT json_schema, system_prompt_plugin FROM industry_schemas
                WHERE industry_type = ?
            """, (industry_type,))
            row = cursor.fetchone()
            if row:
                return {
                    "industry_type": industry_type,
                    "json_schema": json.loads(row["json_schema"]) if isinstance(row["json_schema"], str) else row["json_schema"],
                    "system_prompt_plugin": row["system_prompt_plugin"]
                }
        return None

    def log_api_usage(self, tenant_id: str, industry_type: str, doc_type: str, input_tokens: int, output_tokens: int, status: str) -> None:
        """【マネタイズ機能】APIのトークン消費量と利用ステータスをロギング"""
        with get_sqlite_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO usage_logs (tenant_id, industry_type, doc_type, input_tokens, output_tokens, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (tenant_id, industry_type, doc_type, input_tokens, output_tokens, status))
            conn.commit()

tenant_repository = SharedTenantRepository()