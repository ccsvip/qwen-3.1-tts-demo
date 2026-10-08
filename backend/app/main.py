import logging
from contextlib import asynccontextmanager
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, ValidationError

from app import db
from app.catalog import load_catalog, system_voice_ids
from app.config import (
    MODEL,
    SAMPLE_RATE,
    api_key,
    media_dir,
    public_base_url,
    workspace_id,
)
from app.dashscope_client import (
    DashScopeError,
    enroll_voice,
    is_missing_voice,
    list_enrolled,
    remove_voice,
    stream_tts,
)
from app.listing import merge_cloned_voices
from app.sse import encode_sse
from app.validate import (
    SAFE_MEDIA_RE,
    audio_extension,
    check_audio_size,
    check_instruction,
    check_language,
    check_pitch,
    check_prefix,
    check_public_http_url,
    check_rate,
    check_text,
    check_voice,
    check_volume,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("tts")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_db()
    media_dir().mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="qwen-audio-3.1-tts-flash", lifespan=lifespan)


class TtsBody(BaseModel):
    text: str
    voice: str
    rate: float = 1.0
    volume: int = 50
    pitch: float = 1.0
    instruction: str = ""
    language_hint: str = ""


class CloneBody(BaseModel):
    prefix: str
    display_name: str = ""
    language: str = "zh"
    url: str = ""


def http_error(error: DashScopeError) -> HTTPException:
    status = error.status if error.status in {400, 401, 403} else 502
    return HTTPException(status_code=status, detail=error.message)


def _fail(message: str, status: int = 400) -> None:
    raise HTTPException(status_code=status, detail=message)


def _check_tts(body: TtsBody) -> str:
    text = body.text.strip()
    for message in (
        check_text(text),
        check_voice(body.voice.strip()),
        check_rate(body.rate),
        check_volume(body.volume),
        check_pitch(body.pitch),
        check_instruction(body.instruction.strip()),
        check_language(body.language_hint.strip(), allow_empty=True),
    ):
        if message:
            _fail(message)
    return text


@app.get("/api/health")
def health() -> dict:
    host = ""
    try:
        host = urlparse(public_endpoint_host()).hostname or ""
    except DashScopeError:
        host = ""
    return {
        "ok": True,
        "model": MODEL,
        "has_api_key": bool(api_key()),
        "workspace_configured": bool(workspace_id()),
        "public_base_configured": bool(public_base_url()),
        "endpoint_host": host,
    }


def public_endpoint_host() -> str:
    from app.config import base_url

    try:
        return base_url()
    except ValueError as exc:
        raise DashScopeError(str(exc), status=500) from exc


@app.get("/api/voices")
async def voices() -> dict:
    remote_error = None
    remote: list[dict] = []
    if not api_key():
        remote_error = "未配置 DASHSCOPE_API_KEY，云端复刻音色无法拉取。"
    else:
        try:
            remote = await list_enrolled()
        except DashScopeError as exc:
            log.warning("list voices failed: %s", exc.message)
            remote_error = exc.message
    cloned = merge_cloned_voices(db.list_voices(), remote, remote_error)
    catalog = load_catalog()
    return {
        "model": catalog["model"],
        "groups": catalog["groups"],
        "cloned": cloned,
        "remote_error": remote_error,
    }


@app.post("/api/tts/stream")
async def tts_stream(body: TtsBody) -> StreamingResponse:
    text = _check_tts(body)
    if not api_key():
        raise http_error(
            DashScopeError(
                "未配置 DASHSCOPE_API_KEY。请在 backend/.env 填入百炼北京地域的 API Key，然后重启 backend 容器。",
                status=400,
            )
        )

    async def generate():
        yield encode_sse(
            "meta",
            {
                "sample_rate": SAMPLE_RATE,
                "channels": 1,
                "encoding": "pcm_s16le",
            },
        )
        try:
            async for item in stream_tts(
                text=text,
                voice=body.voice.strip(),
                rate=body.rate,
                volume=body.volume,
                pitch=body.pitch,
                instruction=body.instruction.strip(),
                language_hint=body.language_hint.strip(),
            ):
                yield encode_sse(item["event"], item["data"])
        except DashScopeError as exc:
            log.warning(
                "tts failed status=%s request_id=%s message=%s",
                exc.status,
                exc.request_id,
                exc.message,
            )
            yield encode_sse(
                "error",
                {"message": exc.message, "request_id": exc.request_id},
            )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _clone_fields(request: Request) -> tuple[CloneBody, bytes | None, str, str]:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            payload = await request.json()
        except Exception:
            _fail("请求格式不正确")
        if not isinstance(payload, dict):
            _fail("请求格式不正确")
        try:
            body = CloneBody.model_validate(payload)
        except ValidationError:
            _fail("请求格式不正确")
        return body, None, "", ""
    form = await request.form()
    body = CloneBody(
        prefix=str(form.get("prefix") or ""),
        display_name=str(form.get("display_name") or ""),
        language=str(form.get("language") or "zh"),
        url=str(form.get("url") or ""),
    )
    upload = form.get("file")
    filename = getattr(upload, "filename", "") or ""
    if upload is None or not filename:
        return body, None, "", ""
    data = await upload.read()
    content_type = getattr(upload, "content_type", "") or ""
    return body, data, filename, content_type


@app.post("/api/voices/clone")
async def clone_voice(request: Request) -> JSONResponse:
    body, file_bytes, filename, file_type = await _clone_fields(request)
    prefix = body.prefix.strip()
    display_name = body.display_name.strip() or prefix
    language = (body.language or "zh").strip()
    for message in (
        check_prefix(prefix),
        check_language(language),
        None if display_name and len(display_name) <= 40 else "显示名需要 1 到 40 个字",
    ):
        if message:
            _fail(message)

    saved_name = ""
    source_url = body.url.strip()
    if file_bytes is not None:
        size_error = check_audio_size(len(file_bytes))
        if size_error:
            _fail(size_error)
        extension = audio_extension(file_type, filename)
        if not extension:
            _fail("只支持 wav、mp3、m4a")
        public = public_base_url()
        public_error = check_public_http_url(public, allow_path=False) if public else (
            "本地上传需要公网地址。请在 backend/.env 设置 PUBLIC_BASE_URL，或改为填写百炼能访问的音频 URL。"
        )
        if public_error:
            _fail(public_error)
        saved_name = f"{uuid4().hex}.{extension}"
        target = media_dir() / saved_name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(file_bytes)
        source_url = f"{public}/media/{saved_name}"
    else:
        url_error = check_public_http_url(source_url)
        if url_error:
            _fail(url_error)

    try:
        created = await enroll_voice(prefix=prefix, url=source_url, language=language)
    except DashScopeError as exc:
        if saved_name:
            (media_dir() / saved_name).unlink(missing_ok=True)
        raise http_error(exc) from exc

    db.upsert_voice(
        voice_id=created["voice_id"],
        prefix=prefix,
        display_name=display_name,
        target_model=MODEL,
        language_hint=language,
        source_url=source_url,
        source_filename=saved_name,
    )
    return JSONResponse(
        {
            "voice_id": created["voice_id"],
            "status": created["status"],
            "display_name": display_name,
            "request_id": created.get("request_id"),
        }
    )


@app.delete("/api/voices/{voice_id}")
async def delete_cloned_voice(voice_id: str) -> dict:
    if check_voice(voice_id) is not None or voice_id in system_voice_ids():
        _fail("只能删除复刻音色")
    local = db.get_voice(voice_id)
    try:
        await remove_voice(voice_id)
    except DashScopeError as exc:
        if not (local and is_missing_voice(exc)):
            if local is None:
                raise http_error(exc) from exc
            raise http_error(exc) from exc
    if local and local.get("source_filename"):
        name = local["source_filename"]
        if SAFE_MEDIA_RE.fullmatch(name):
            (media_dir() / name).unlink(missing_ok=True)
    db.delete_voice(voice_id)
    return {"deleted": True, "voice_id": voice_id}


@app.get("/media/{name}")
def media(name: str) -> FileResponse:
    if not SAFE_MEDIA_RE.fullmatch(name):
        _fail("文件不存在", 404)
    path = media_dir() / name
    if not path.is_file():
        _fail("文件不存在", 404)
    media_type = {
        "wav": "audio/wav",
        "mp3": "audio/mpeg",
        "m4a": "audio/mp4",
    }[name.rsplit(".", 1)[-1]]
    return FileResponse(path, media_type=media_type)
