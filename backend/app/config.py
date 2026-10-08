import os
import re
from pathlib import Path

MODEL = "qwen-audio-3.1-tts-flash"
SAMPLE_RATE = 24000
MAX_TEXT_CHARS = 2000
MAX_AUDIO_BYTES = 10 * 1024 * 1024
WORKSPACE_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def api_key() -> str:
    return os.environ.get("DASHSCOPE_API_KEY", "").strip()


def workspace_id() -> str:
    return os.environ.get("WORKSPACE_ID", "").strip()


def base_url() -> str:
    explicit = os.environ.get("DASHSCOPE_BASE_URL", "").strip().rstrip("/")
    if explicit:
        return explicit
    workspace = workspace_id()
    if workspace:
        if not WORKSPACE_RE.fullmatch(workspace):
            raise ValueError("WORKSPACE_ID 只能包含字母、数字、下划线和短横线")
        return f"https://{workspace}.cn-beijing.maas.aliyuncs.com/api/v1"
    return "https://dashscope.aliyuncs.com/api/v1"


def public_base_url() -> str:
    return os.environ.get("PUBLIC_BASE_URL", "").strip().rstrip("/")


def data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "/data"))


def database_path() -> Path:
    override = os.environ.get("DATABASE_PATH", "").strip()
    if override:
        return Path(override)
    return data_dir() / "app.db"


def media_dir() -> Path:
    return data_dir() / "media"
