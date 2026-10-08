from app.catalog import load_catalog, system_voice_ids
from app.config import MODEL
from app.listing import is_ready, merge_cloned_voices, prefix_of
from app.validate import check_prefix, check_public_http_url


def test_catalog_voice_ids_are_unique_and_complete():
    catalog = load_catalog()
    assert catalog["model"] == MODEL
    counts = {group["id"]: len(group["voices"]) for group in catalog["groups"]}
    assert counts == {
        "multilingual": 4,
        "chinese": 22,
        "english": 15,
        "more": 27,
    }
    ids = []
    for group in catalog["groups"]:
        ids.extend(voice["voice"] for voice in group["voices"])
    assert len(ids) == len(set(ids)) == 68
    assert "longanhuan_v3.1" in ids
    assert "Emily_v3.1" in ids
    assert system_voice_ids() == set(ids)


def test_prefix_rules():
    assert check_prefix("myvoice") is None
    assert check_prefix("my-voice") is not None
    assert check_prefix("") is not None
    assert check_prefix("a" * 11) is not None


def test_public_url_rejects_loopback_and_private_ips():
    assert check_public_http_url("https://cdn.example.com/a.wav") is None
    assert check_public_http_url("http://127.0.0.1/a.wav") is not None
    assert check_public_http_url("http://192.168.1.8/a.wav") is not None
    assert check_public_http_url("not a url") is not None
    assert (
        check_public_http_url("https://example.com/app", allow_path=False) is not None
    )


def test_merge_hides_other_models_and_keeps_local_names():
    local = [
        {
            "voice_id": f"{MODEL}-myvoice-abc",
            "prefix": "myvoice",
            "display_name": "我的声音",
            "language_hint": "zh",
            "source_url": "https://cdn.example.com/a.wav",
            "created_at": "2026-10-08T00:00:00+00:00",
        }
    ]
    remote = [
        {"voice_id": f"{MODEL}-myvoice-abc", "status": "OK", "gmt_create": ""},
        {"voice_id": f"{MODEL}-other-xyz", "status": "DEPLOYING", "gmt_create": ""},
        {"voice_id": "cosyvoice-v3-flash-myvoice-nope", "status": "OK", "gmt_create": ""},
    ]
    merged = merge_cloned_voices(local, remote, None)
    by_id = {item["voice_id"]: item for item in merged}
    assert "cosyvoice-v3-flash-myvoice-nope" not in by_id
    assert by_id[f"{MODEL}-myvoice-abc"]["display_name"] == "我的声音"
    assert by_id[f"{MODEL}-other-xyz"]["status"] == "DEPLOYING"
    assert prefix_of(f"{MODEL}-other-xyz") == "other"
    assert is_ready("OK")
    assert not is_ready("DEPLOYING")


def test_local_voice_remains_when_remote_list_fails():
    local = [
        {
            "voice_id": "custom-1",
            "prefix": "custom",
            "display_name": "本地",
            "language_hint": "zh",
            "source_url": "",
            "created_at": "2026-10-08T00:00:00+00:00",
        }
    ]
    merged = merge_cloned_voices(local, [], "网络失败")
    assert merged[0]["display_name"] == "本地"
    assert merged[0]["status"] == "OK"
    assert merged[0]["on_remote"] is False
