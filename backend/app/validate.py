import ipaddress
import re
from urllib.parse import urlparse

from app.config import MAX_AUDIO_BYTES, MAX_TEXT_CHARS

PREFIX_RE = re.compile(r"^[A-Za-z0-9]{1,10}$")
SAFE_MEDIA_RE = re.compile(r"^[a-f0-9]{32}\.(wav|mp3|m4a)$")

LANGUAGES = (
    "zh",
    "en",
    "fr",
    "de",
    "ja",
    "ko",
    "ru",
    "pt",
    "th",
    "id",
    "vi",
    "es",
    "it",
    "ms",
    "fil",
    "ar",
)

AUDIO_EXTENSIONS = {
    "audio/wav": "wav",
    "audio/wave": "wav",
    "audio/x-wav": "wav",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/mp4": "m4a",
    "audio/m4a": "m4a",
    "audio/x-m4a": "m4a",
}


def check_prefix(prefix: str) -> str | None:
    if not PREFIX_RE.fullmatch(prefix or ""):
        return "前缀只能是字母和数字，最多 10 位"
    return None


def check_language(language: str, *, allow_empty: bool = False) -> str | None:
    if not language:
        return None if allow_empty else "请选择样本语种"
    if language not in LANGUAGES:
        return "不支持的语种"
    return None


def check_text(text: str) -> str | None:
    cleaned = (text or "").strip()
    if not cleaned:
        return "请输入要合成的文字"
    if len(cleaned) > MAX_TEXT_CHARS:
        return f"文本不能超过 {MAX_TEXT_CHARS} 字"
    return None


def check_voice(voice: str) -> str | None:
    if not voice or len(voice) > 200 or any(ch.isspace() for ch in voice):
        return "请选择音色"
    return None


def check_rate(rate: float) -> str | None:
    if rate < 0.5 or rate > 2:
        return "语速范围是 0.5 到 2"
    return None


def check_volume(volume: int) -> str | None:
    if volume < 0 or volume > 100:
        return "音量范围是 0 到 100"
    return None


def check_pitch(pitch: float) -> str | None:
    if pitch < 0.5 or pitch > 2:
        return "音调范围是 0.5 到 2"
    return None


def check_instruction(instruction: str) -> str | None:
    if len(instruction or "") > 300:
        return "指令不能超过 300 字"
    return None


def _host_is_private(host: str) -> bool:
    lowered = host.lower().rstrip(".")
    if lowered in {"localhost", "0.0.0.0", "::1"} or lowered.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(lowered)
    except ValueError:
        return False
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
    )


def check_public_http_url(url: str, *, allow_path: bool = True) -> str | None:
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return "音频地址需要是 http 或 https URL"
    if _host_is_private(parsed.hostname):
        return "百炼服务器访问不到本机或内网地址，请填写公网 URL"
    if not allow_path and parsed.path not in {"", "/"}:
        return "PUBLIC_BASE_URL 请填写站点根地址，不要带子路径"
    return None


def audio_extension(content_type: str, filename: str) -> str | None:
    ext = AUDIO_EXTENSIONS.get((content_type or "").split(";")[0].strip().lower())
    if ext:
        return ext
    suffix = ""
    if filename and "." in filename:
        suffix = filename.rsplit(".", 1)[-1].lower()
    if suffix in {"wav", "mp3", "m4a"}:
        return suffix
    return None


def check_audio_size(size: int) -> str | None:
    if size <= 0:
        return "音频文件是空的"
    if size > MAX_AUDIO_BYTES:
        return "音频不能超过 10MB"
    return None
