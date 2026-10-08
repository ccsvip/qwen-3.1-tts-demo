import pytest
from fastapi.testclient import TestClient

from app.dashscope_client import DashScopeError


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-test")
    monkeypatch.delenv("DASHSCOPE_BASE_URL", raising=False)
    monkeypatch.delenv("WORKSPACE_ID", raising=False)
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)

    async def empty_remote():
        return []

    monkeypatch.setattr("app.main.list_enrolled", empty_remote)
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["model"] == "qwen-audio-3.1-tts-flash"
    assert body["has_api_key"] is True


def test_voices_lists_system_catalog(client):
    response = client.get("/api/voices")
    assert response.status_code == 200
    body = response.json()
    assert len(body["groups"]) == 4
    assert body["cloned"] == []
    assert body["remote_error"] is None


def test_stream_requires_text(client):
    response = client.post("/api/tts/stream", json={"text": "  ", "voice": "longanhuan_v3.1"})
    assert response.status_code == 400
    assert "文字" in response.json()["detail"]


def test_stream_proxies_pcm_events(client, monkeypatch):
    async def fake_stream(**kwargs):
        assert kwargs["text"] == "你好"
        assert kwargs["voice"] == "longanhuan_v3.1"
        assert kwargs["instruction"] == "用重庆话说"
        yield {"event": "sentence", "data": {"text": "你好", "index": 0}}
        yield {"event": "audio", "data": {"pcm": "AQID"}}
        yield {"event": "done", "data": {"request_id": "r1", "usage": {"total_tokens": 3}}}

    monkeypatch.setattr("app.main.stream_tts", fake_stream)
    response = client.post(
        "/api/tts/stream",
        json={
            "text": "你好",
            "voice": "longanhuan_v3.1",
            "instruction": "用重庆话说",
            "language_hint": "zh",
        },
    )
    assert response.status_code == 200
    assert "event: meta" in response.text
    assert "event: sentence" in response.text
    assert "event: audio" in response.text
    assert "pcm_s16le" in response.text


def test_stream_without_key(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DASHSCOPE_API_KEY", "")
    from app.main import app

    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/tts/stream",
            json={"text": "你好", "voice": "longanhuan_v3.1"},
        )
    assert response.status_code == 400
    assert "DASHSCOPE_API_KEY" in response.json()["detail"]


def test_clone_rejects_private_url_without_calling_upstream(client, monkeypatch):
    async def boom(**kwargs):
        raise AssertionError("should not enroll")

    monkeypatch.setattr("app.main.enroll_voice", boom)
    response = client.post(
        "/api/voices/clone",
        json={
            "prefix": "myvoice",
            "display_name": "甲",
            "language": "zh",
            "url": "http://127.0.0.1/a.wav",
        },
    )
    assert response.status_code == 400
    assert "公网" in response.json()["detail"]


def test_clone_upload_requires_public_base(client, monkeypatch):
    async def boom(**kwargs):
        raise AssertionError("should not enroll")

    monkeypatch.setattr("app.main.enroll_voice", boom)
    response = client.post(
        "/api/voices/clone",
        data={"prefix": "myvoice", "display_name": "甲", "language": "zh"},
        files={"file": ("demo.wav", b"RIFFdemo", "audio/wav")},
    )
    assert response.status_code == 400
    assert "PUBLIC_BASE_URL" in response.json()["detail"]


def test_clone_saves_local_name(client, monkeypatch):
    async def fake_enroll(**kwargs):
        assert kwargs["url"] == "https://cdn.example.com/a.wav"
        assert kwargs["prefix"] == "myvoice"
        return {"voice_id": "qwen-audio-3.1-tts-flash-myvoice-abc", "status": "OK", "request_id": "r"}

    monkeypatch.setattr("app.main.enroll_voice", fake_enroll)
    response = client.post(
        "/api/voices/clone",
        json={
            "prefix": "myvoice",
            "display_name": "书房",
            "language": "zh",
            "url": "https://cdn.example.com/a.wav",
        },
    )
    assert response.status_code == 200
    assert response.json()["voice_id"].endswith("myvoice-abc")

    async def remote():
        return [
            {
                "voice_id": "qwen-audio-3.1-tts-flash-myvoice-abc",
                "status": "OK",
                "gmt_create": "",
            }
        ]

    monkeypatch.setattr("app.main.list_enrolled", remote)
    listing = client.get("/api/voices")
    cloned = listing.json()["cloned"]
    assert cloned[0]["display_name"] == "书房"


def test_delete_system_voice_is_rejected(client, monkeypatch):
    async def boom(voice_id):
        raise AssertionError(voice_id)

    monkeypatch.setattr("app.main.remove_voice", boom)
    response = client.delete("/api/voices/longanhuan_v3.1")
    assert response.status_code == 400


def test_delete_missing_remote_still_drops_local_row(client, monkeypatch):
    from app import db
    from app.config import MODEL

    voice_id = f"{MODEL}-myvoice-abc"
    db.upsert_voice(
        voice_id=voice_id,
        prefix="myvoice",
        display_name="书房",
        target_model=MODEL,
        language_hint="zh",
        source_url="https://cdn.example.com/a.wav",
        source_filename="",
    )

    async def missing(voice_id):
        raise DashScopeError("voice not found", status=400)

    monkeypatch.setattr("app.main.remove_voice", missing)
    response = client.delete(f"/api/voices/{voice_id}")
    assert response.status_code == 200
    assert db.get_voice(voice_id) is None
