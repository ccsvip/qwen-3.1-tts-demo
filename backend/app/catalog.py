import json
from functools import lru_cache
from pathlib import Path

CATALOG_PATH = Path(__file__).with_name("voices.json")


@lru_cache(maxsize=1)
def load_catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def system_voice_ids() -> set[str]:
    found: set[str] = set()
    for group in load_catalog()["groups"]:
        for voice in group["voices"]:
            found.add(voice["voice"])
    return found
