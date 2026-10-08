import json
import logging
from collections.abc import AsyncIterator

import httpx

from app.config import MODEL, SAMPLE_RATE, api_key, base_url
from app.sse import SseParser

log = logging.getLogger("tts")

CUSTOMIZATION_PATH = "/services/audio/tts/customization"
SYNTH_PATH = "/services/audio/tts/SpeechSynthesizer"


class DashScopeError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status: int = 502,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.request_id = request_id


def require_key() -> str:
    key = api_key()
    if not key:
        raise DashScopeError(
            "未配置 DASHSCOPE_API_KEY。请在 backend/.env 填入百炼北京地域的 API Key，然后重启 backend 容器。",
            status=400,
        )
    return key


def endpoint(path: str) -> str:
    try:
        root = base_url()
    except ValueError as exc:
        raise DashScopeError(str(exc), status=500) from exc
    return root.rstrip("/") + path


def raise_for_api(status: int, payload: object) -> None:
    if not isinstance(payload, dict):
        if status >= 400:
            raise DashScopeError("百炼请求失败", status=status if status < 500 else 502)
        return
    code = payload.get("code")
    if code:
        message = str(payload.get("message") or code)
        http_status = status if status in {400, 401, 403} else 502
        raise DashScopeError(
            message,
            status=http_status,
            request_id=payload.get("request_id"),
        )
    if status >= 400:
        message = str(payload.get("message") or "百炼请求失败")
        raise DashScopeError(
            message,
            status=status if status < 500 else 502,
            request_id=payload.get("request_id"),
        )


def build_tts_body(
    *,
    text: str,
    voice: str,
    rate: float,
    volume: int,
    pitch: float,
    instruction: str,
    language_hint: str,
) -> dict:
    item: dict = {
        "text": text,
        "voice": voice,
        "format": "pcm",
        "sample_rate": SAMPLE_RATE,
        "volume": volume,
        "rate": rate,
        "pitch": pitch,
    }
    if language_hint:
        item["language_hints"] = [language_hint]
    if instruction:
        item["instruction"] = instruction
    return {"model": MODEL, "input": item}


def interpret_tts_payload(payload: dict) -> list[dict]:
    if payload.get("code"):
        return [
            {
                "event": "error",
                "data": {
                    "message": str(payload.get("message") or payload.get("code")),
                    "request_id": payload.get("request_id"),
                },
            }
        ]
    output = payload.get("output") or {}
    events: list[dict] = []
    if output.get("type") == "sentence-begin" and output.get("original_text"):
        sentence = output.get("sentence") or {}
        events.append(
            {
                "event": "sentence",
                "data": {
                    "text": output["original_text"],
                    "index": sentence.get("index"),
                },
            }
        )
    audio = (output.get("audio") or {}).get("data") or ""
    if audio:
        events.append({"event": "audio", "data": {"pcm": audio}})
    if output.get("finish_reason") == "stop":
        usage = payload.get("usage") or {}
        events.append(
            {
                "event": "done",
                "data": {
                    "request_id": payload.get("request_id"),
                    "usage": {
                        "input_tokens": usage.get("input_tokens"),
                        "output_tokens": usage.get("output_tokens"),
                        "total_tokens": usage.get("total_tokens"),
                        "characters": usage.get("characters"),
                    },
                },
            }
        )
    return events


def _auth_headers(key: str, *, sse: bool) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if sse:
        headers["X-DashScope-SSE"] = "enable"
        headers["Accept"] = "text/event-stream"
    return headers


def _loads_json(text: str) -> dict:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DashScopeError("百炼返回了无法解析的内容", status=502) from exc
    if not isinstance(payload, dict):
        raise DashScopeError("百炼返回了无法解析的内容", status=502)
    return payload


async def post_json(path: str, payload: dict, *, read_timeout: float = 60) -> dict:
    key = require_key()
    timeout = httpx.Timeout(10.0, read=read_timeout)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                endpoint(path),
                json=payload,
                headers=_auth_headers(key, sse=False),
            )
    except httpx.TimeoutException as exc:
        raise DashScopeError("连接百炼超时", status=502) from exc
    except httpx.HTTPError as exc:
        log.warning("dashscope transport error: %s", exc.__class__.__name__)
        raise DashScopeError("连接百炼失败", status=502) from exc
    data = _loads_json(response.text)
    raise_for_api(response.status_code, data)
    return data


def _voice_list(payload: dict) -> list[dict]:
    output = payload.get("output") or {}
    for key in ("voice_list", "voices", "list"):
        value = output.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def normalize_remote_voice(item: dict) -> dict:
    return {
        "voice_id": item.get("voice_id") or item.get("voice") or "",
        "status": item.get("status") or "OK",
        "gmt_create": item.get("gmt_create") or item.get("created_at") or "",
    }


async def list_enrolled() -> list[dict]:
    found: list[dict] = []
    seen: set[str] = set()
    for page in range(20):
        payload = await post_json(
            CUSTOMIZATION_PATH,
            {
                "model": "voice-enrollment",
                "input": {
                    "action": "list_voice",
                    "page_index": page,
                    "page_size": 100,
                },
            },
        )
        items = _voice_list(payload)
        if not items:
            break
        added = 0
        for item in items:
            voice = normalize_remote_voice(item)
            voice_id = voice["voice_id"]
            if not voice_id or voice_id in seen:
                continue
            seen.add(voice_id)
            found.append(voice)
            added += 1
        if added == 0 or len(items) < 100:
            break
    return found


async def query_voice(voice_id: str) -> dict:
    payload = await post_json(
        CUSTOMIZATION_PATH,
        {
            "model": "voice-enrollment",
            "input": {"action": "query_voice", "voice_id": voice_id},
        },
    )
    output = payload.get("output") or {}
    if isinstance(output, dict) and (
        "status" in output or "voice_id" in output or "voice" in output
    ):
        return normalize_remote_voice(output)
    items = _voice_list(payload)
    if items:
        return normalize_remote_voice(items[0])
    return {"voice_id": voice_id, "status": "UNKNOWN", "gmt_create": ""}


async def enroll_voice(*, prefix: str, url: str, language: str) -> dict:
    import asyncio

    payload = await post_json(
        CUSTOMIZATION_PATH,
        {
            "model": "voice-enrollment",
            "input": {
                "action": "create_voice",
                "target_model": MODEL,
                "prefix": prefix,
                "url": url,
                "language_hints": [language],
            },
        },
        read_timeout=120,
    )
    output = payload.get("output") or {}
    voice_id = output.get("voice_id") or output.get("voice")
    if not voice_id:
        raise DashScopeError(
            "百炼没有返回音色 ID",
            status=502,
            request_id=payload.get("request_id"),
        )
    status = "UNKNOWN"
    try:
        for _ in range(8):
            info = await query_voice(voice_id)
            status = str(info.get("status") or "UNKNOWN").upper()
            if status in {"OK", "SUCCESS", "FAILED", "UNDEPLOYED"}:
                break
            await asyncio.sleep(1)
    except DashScopeError:
        log.warning("query after enroll failed voice_id=%s", voice_id)
    return {
        "voice_id": voice_id,
        "status": status,
        "request_id": payload.get("request_id"),
    }


def is_missing_voice(error: DashScopeError) -> bool:
    text = (error.message or "").lower()
    return (
        "not found" in text
        or "notfound" in text
        or "does not exist" in text
        or "不存在" in text
    )


async def remove_voice(voice_id: str) -> None:
    await post_json(
        CUSTOMIZATION_PATH,
        {
            "model": "voice-enrollment",
            "input": {"action": "delete_voice", "voice_id": voice_id},
        },
    )


async def stream_tts(
    *,
    text: str,
    voice: str,
    rate: float,
    volume: int,
    pitch: float,
    instruction: str,
    language_hint: str,
) -> AsyncIterator[dict]:
    key = require_key()
    body = build_tts_body(
        text=text,
        voice=voice,
        rate=rate,
        volume=volume,
        pitch=pitch,
        instruction=instruction,
        language_hint=language_hint,
    )
    timeout = httpx.Timeout(10.0, read=300.0)
    parser = SseParser()
    yielded = False
    raw_parts: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                endpoint(SYNTH_PATH),
                json=body,
                headers=_auth_headers(key, sse=True),
            ) as response:
                if response.status_code >= 400:
                    raw = await response.aread()
                    payload = _loads_json(raw.decode("utf-8", errors="replace"))
                    raise_for_api(response.status_code, payload)
                    return
                async for chunk in response.aiter_text():
                    raw_parts.append(chunk)
                    for event in parser.feed(chunk):
                        yielded = True
                        for item in _events_from_sse(event):
                            yield item
                for event in parser.flush():
                    yielded = True
                    for item in _events_from_sse(event):
                        yield item
    except DashScopeError:
        raise
    except httpx.TimeoutException as exc:
        raise DashScopeError("百炼响应超时", status=502) from exc
    except httpx.HTTPError as exc:
        log.warning("tts transport error: %s", exc.__class__.__name__)
        raise DashScopeError("连接百炼失败", status=502) from exc

    if yielded:
        return
    raw_text = "".join(raw_parts).strip()
    if not raw_text:
        raise DashScopeError("百炼没有返回音频", status=502)
    payload = _loads_json(raw_text)
    raise_for_api(200, payload)
    items = interpret_tts_payload(payload)
    if not items:
        raise DashScopeError("百炼没有返回音频", status=502)
    for item in items:
        yield item


def _events_from_sse(event: dict) -> list[dict]:
    try:
        payload = json.loads(event["data"])
    except json.JSONDecodeError:
        return [
            {
                "event": "error",
                "data": {"message": "百炼返回了无法解析的音频流"},
            }
        ]
    if not isinstance(payload, dict):
        return []
    return interpret_tts_payload(payload)
