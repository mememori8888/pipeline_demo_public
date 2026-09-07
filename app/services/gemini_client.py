from functools import lru_cache
from typing import Optional

from google import genai
from google.genai import types

from app.core.config import settings


def _vertex_project() -> str:
    return (settings.GOOGLE_CLOUD_PROJECT or settings.CLOUD_RUN_PROJECT_ID).strip()


@lru_cache(maxsize=4)
def get_gemini_client(timeout_ms: Optional[int] = None):
    project = _vertex_project()
    location = settings.GOOGLE_CLOUD_LOCATION.strip() or "global"
    if not project:
        raise RuntimeError(
            "GOOGLE_CLOUD_PROJECT is required for Vertex AI Gemini calls. "
            "Set it on Cloud Run and grant the runtime service account roles/aiplatform.user."
        )

    return genai.Client(
        vertexai=True,
        project=project,
        location=location,
        http_options=types.HttpOptions(
            apiVersion="v1",
            timeout=timeout_ms or settings.GEMINI_HTTP_TIMEOUT_MS,
        ),
    )
