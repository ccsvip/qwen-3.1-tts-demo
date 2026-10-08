from app.config import MODEL

READY_STATUSES = {"OK", "SUCCESS"}


def prefix_of(voice_id: str) -> str:
    marker = MODEL + "-"
    if not voice_id.startswith(marker):
        return ""
    rest = voice_id[len(marker) :]
    return rest.split("-", 1)[0]


def merge_cloned_voices(
    local_rows: list[dict],
    remote_items: list[dict],
    remote_error: str | None,
) -> list[dict]:
    local_map = {row["voice_id"]: row for row in local_rows}
    remote_map = {
        item["voice_id"]: item for item in remote_items if item.get("voice_id")
    }
    ordered: list[str] = []
    for voice_id in remote_map:
        if voice_id.startswith(MODEL + "-") or voice_id in local_map:
            ordered.append(voice_id)
    for voice_id in local_map:
        if voice_id not in ordered:
            ordered.append(voice_id)

    merged: list[dict] = []
    for voice_id in ordered:
        local = local_map.get(voice_id)
        remote = remote_map.get(voice_id, {})
        if remote:
            status = str(remote.get("status") or "OK")
        elif remote_error and local:
            status = "OK"
        else:
            status = "UNKNOWN"
        merged.append(
            {
                "voice_id": voice_id,
                "display_name": (local or {}).get("display_name") or voice_id,
                "prefix": (local or {}).get("prefix") or prefix_of(voice_id),
                "status": status,
                "language_hint": (local or {}).get("language_hint") or "",
                "source_url": (local or {}).get("source_url") or "",
                "created_at": (local or {}).get("created_at")
                or remote.get("gmt_create")
                or "",
                "on_remote": voice_id in remote_map,
            }
        )
    return merged


def is_ready(status: str) -> bool:
    return (status or "").upper() in READY_STATUSES
