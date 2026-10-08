import json

from app.dashscope_client import build_tts_body, interpret_tts_payload
from app.sse import SseParser


def test_parser_splits_chunks():
    parser = SseParser()
    raw = 'event: result\ndata: {"a": 1}\n\n'
    assert parser.feed(raw[:8]) == []
    events = parser.feed(raw[8:])
    assert events == [{"event": "result", "data": '{"a": 1}'}]


def test_parser_keeps_audio_events_in_order():
    parser = SseParser()
    raw = (
        "id:1\n"
        "event:result\n"
        ":HTTP_STATUS/200\n"
        'data:{"request_id":"r1","output":{"finish_reason":"null","type":"sentence-begin","original_text":"你好。","audio":{"data":""}}}\n'
        "\n"
        "id:2\n"
        "event:result\n"
        'data:{"request_id":"r1","output":{"finish_reason":"null","type":"sentence-synthesis","audio":{"data":"AQID"}}}\n'
        "\n"
        "id:3\n"
        "event:result\n"
        'data:{"request_id":"r1","output":{"finish_reason":"stop","audio":{"data":""}},"usage":{"input_tokens":1,"output_tokens":2,"total_tokens":3}}\n'
        "\n"
    )
    events = parser.feed(raw)
    assert [event["event"] for event in events] == ["result", "result", "result"]
    interpreted = []
    for event in events:
        interpreted.extend(interpret_tts_payload(json.loads(event["data"])))
    assert [item["event"] for item in interpreted] == ["sentence", "audio", "done"]
    assert interpreted[0]["data"]["text"] == "你好。"
    assert interpreted[1]["data"]["pcm"] == "AQID"
    assert interpreted[2]["data"]["usage"]["total_tokens"] == 3


def test_string_null_finish_reason_is_not_done():
    payload = {
        "output": {"finish_reason": "null", "audio": {"data": ""}},
    }
    assert interpret_tts_payload(payload) == []


def test_error_payload():
    items = interpret_tts_payload(
        {"code": "InvalidParameter", "message": "bad voice", "request_id": "r2"}
    )
    assert items[0]["event"] == "error"
    assert items[0]["data"]["message"] == "bad voice"


def test_build_tts_body_omits_empty_controls():
    body = build_tts_body(
        text="你好",
        voice="longanhuan_v3.1",
        rate=1,
        volume=50,
        pitch=1,
        instruction="",
        language_hint="",
    )
    assert body["model"] == "qwen-audio-3.1-tts-flash"
    assert body["input"]["format"] == "pcm"
    assert body["input"]["sample_rate"] == 24000
    assert "instruction" not in body["input"]
    assert "language_hints" not in body["input"]


def test_build_tts_body_includes_instruction_and_language():
    body = build_tts_body(
        text="你好",
        voice="longanhuan_v3.1",
        rate=1.2,
        volume=70,
        pitch=0.9,
        instruction="用重庆话说",
        language_hint="zh",
    )
    assert body["input"]["instruction"] == "用重庆话说"
    assert body["input"]["language_hints"] == ["zh"]
    assert body["input"]["rate"] == 1.2
