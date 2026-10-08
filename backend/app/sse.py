import json


class SseParser:
    """Parse a DashScope-style SSE byte stream incrementally."""

    def __init__(self) -> None:
        self._buf = ""

    def feed(self, text: str) -> list[dict]:
        self._buf += text.replace("\r\n", "\n").replace("\r", "\n")
        events: list[dict] = []
        while "\n\n" in self._buf:
            raw, self._buf = self._buf.split("\n\n", 1)
            event = self._parse_block(raw)
            if event:
                events.append(event)
        return events

    def flush(self) -> list[dict]:
        if not self._buf.strip():
            self._buf = ""
            return []
        event = self._parse_block(self._buf)
        self._buf = ""
        return [event] if event else []

    def _parse_block(self, raw: str) -> dict | None:
        event_name = "message"
        data_lines: list[str] = []
        for line in raw.split("\n"):
            if not line or line.startswith(":"):
                continue
            if line.startswith("event:"):
                event_name = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
        if not data_lines:
            return None
        return {"event": event_name, "data": "\n".join(data_lines)}


def encode_sse(event: str, data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"
