import os
import sys
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator

class Settings(BaseSettings):
    # 【🔥絶対ガード：古いキーのハードコードを完全消去】
    # default値を設定せず必須（...）にすることで、.envから読み込めない場合は起動時に強制停止させます
    GEMINI_API_KEY: str = Field(..., description="Google Gemini API Key")
    
    # 🌟【新設】YouTube用のAPIキー（未セットの場合は空文字を許容して安全にフォールバック）
    YOUTUBE_API_KEY: str = Field(default="", description="YouTube Data API Key")
    
    # Security (AES-256用 暗号化鍵。これも未指定時はエラーにするか安全なデフォルト値を設定)
    ENCRYPTION_KEY: str = Field(..., description="Encryption key for local PII mappings")
    APP_API_KEY: str = Field(default="", description="Optional API key for public Cloud Run access")
    
    # DB Paths
    SQLITE_DB_PATH: str = Field(default="shared_tenant_store.db")
    CHROMA_DB_DIR: str = Field(default="./chroma_vector_store")
    GOOGLE_DRIVE_INPUT_FOLDER_ID: str = Field(default="")
    GOOGLE_DRIVE_OUTPUT_FOLDER_ID: str = Field(default="")
    CLOUD_RUN_PROJECT_ID: str = Field(default="", description="Google Cloud project that owns the optional Cloud Run batch job")
    CLOUD_RUN_REGION: str = Field(default="asia-northeast1", description="Region that owns the optional Cloud Run batch job")
    CLOUD_RUN_BATCH_JOB_NAME: str = Field(default="", description="Optional Cloud Run Job name for long Google Drive batches")
    CLOUD_RUN_BATCH_JOB_TIMEOUT_SECONDS: int = Field(default=7200, description="Per-execution timeout for Cloud Run batch jobs")
    BATCH_CHUNK_SIZE: int = Field(default=3, description="Number of input files to process before uploading a partial Markdown result")
    BATCH_PAGE_CONCURRENCY: int = Field(default=1, description="Maximum concurrent Gemini page analysis calls")
    BATCH_DELAY_BETWEEN_FILES_SECONDS: float = Field(default=3.0, description="Pause after each file analysis to reduce API pressure")
    BATCH_DELAY_BETWEEN_CHUNKS_SECONDS: float = Field(default=15.0, description="Pause after each chunk output to reduce sustained load")
    BATCH_SYNTHESIS_MAX_CHARS: int = Field(default=600000, description="Maximum source characters to send into the final synthesis call")
    BATCH_KEEP_PART_FILES: bool = Field(default=False, description="Keep temporary chunk Markdown files after the final integrated output is created")
    GEMINI_HTTP_TIMEOUT_MS: int = Field(default=300000, description="Gemini API request timeout in milliseconds")
    GEMINI_MAX_RETRIES: int = Field(default=3, description="Maximum Gemini retries for temporary failures")
    GEMINI_RETRY_BASE_DELAY_SECONDS: float = Field(default=30.0, description="Base delay for Gemini temporary-error retry backoff")
    
    # LLM Settings
    DEFAULT_MODEL_ID: str = Field(default="gemini-2.5-flash")

    @field_validator(
        "GEMINI_API_KEY",
        "YOUTUBE_API_KEY",
        "ENCRYPTION_KEY",
        "APP_API_KEY",
        "GOOGLE_DRIVE_INPUT_FOLDER_ID",
        "GOOGLE_DRIVE_OUTPUT_FOLDER_ID",
        "CLOUD_RUN_PROJECT_ID",
        "CLOUD_RUN_REGION",
        "CLOUD_RUN_BATCH_JOB_NAME",
        mode="before",
    )
    @classmethod
    def strip_env_values(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value

    # Pydantic Settingsに、カレントディレクトリの「.env」を強制的に探しに行かせる明示的定義
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

try:
    # 起動テストとロード
    settings = Settings()
except Exception as e:
    # 【フェイルセーフ】設定の読み込みに失敗した場合、Uvicornを立ち上げず親切なメッセージを出して終了
    print("\n" + "="*60)
    print("[❌ 起動クラッシュを検知: 環境変数のガードレールが作動しました]")
    print(f"詳細エラー: {str(e)}")
    print("\n[原因]")
    print("プロジェクトのルート（appフォルダと同じ階層）に「.env」ファイルが存在しないか、")
    print("中に有効な『GEMINI_API_KEY』が記述されていません。")
    print("\n[対策]")
    print("1. ルート階層に「.env」という名前のファイルを新規作成してください。")
    print("2. ファイル内に以下のように記述して保存してください（※前後に余計な文字や空白を入れない）")
    print('   GEMINI_API_KEY="あなたの最新のGeminiAPIキー"')
    print('   ENCRYPTION_KEY="your-32-byte-encryption-key"')
    print('   YOUTUBE_API_KEY="あなたのYouTube APIキー（任意）"')
    print("="*60 + "\n")
    sys.exit(1)
