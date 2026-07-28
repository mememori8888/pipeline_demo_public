import sqlite3
import os
import chromadb
from app.core.config import settings

def get_sqlite_conn():
    """SQLite接続を取得するコンテキスト用関数"""
    conn = sqlite3.connect(settings.SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_databases():
    """アプリケーション起動時にデータベースとテーブルを初期化（フェイルセーフ）"""
    # 1. SQLite初期化
    with get_sqlite_conn() as conn:
        cursor = conn.cursor()
        
        # 利用量・トークン消費量トラッキングテーブル
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usage_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                industry_type TEXT NOT NULL,
                doc_type TEXT NOT NULL,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                api_call_count INTEGER DEFAULT 1,
                status TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # PII暗号化復元マップテーブル
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pii_maps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                masked_token TEXT NOT NULL,
                encrypted_original_value TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 動的JSONスキーマ・プロンプト管理テーブル（★収益化のコア）
        # 【🔥構文バグ修正箇所】SQL文字列内に混入していたPythonコメント(#)を完全に排除
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS industry_schemas (
                industry_type TEXT PRIMARY KEY,
                json_schema TEXT NOT NULL,
                system_prompt_plugin TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 初期シードデータ（業界指定がない場合のデフォルト汎用スキーマをフールプルーフとして登録）
        cursor.execute("""
            INSERT OR IGNORE INTO industry_schemas (industry_type, json_schema, system_prompt_plugin)
            VALUES (
                'generic_document',
                '{"type": "object", "properties": {"document_title": {"type": "string"}, "summary": {"type": "string"}, "extracted_key_values": {"type": "object"}}, "required": ["document_title", "summary", "extracted_key_values"]}',
                '提供された手書き、または印刷されたドキュメントの全体構造を解析し、タイトル、要約、および主要なキーと値のペアを抽出してください。'
            )
        """)
        conn.commit()

    # 2. ChromaDB初期化
    os.makedirs(settings.CHROMA_DB_DIR, exist_ok=True)
    chroma_client = chromadb.PersistentClient(path=settings.CHROMA_DB_DIR)
    return chroma_client

# アプリケーションロード時に、インポートをトリガーとして自動初期化を実行
chroma_client = init_databases()