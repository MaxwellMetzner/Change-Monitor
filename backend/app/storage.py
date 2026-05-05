from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import settings


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def relative_to_data(path: Path) -> str:
    return path.resolve().relative_to(settings.DATA_DIR).as_posix()


def data_path(relative_path: str | None) -> Path | None:
    if not relative_path:
        return None
    return (settings.DATA_DIR / relative_path).resolve()


def asset_url(relative_path: str | None) -> str | None:
    if not relative_path:
        return None
    return f"/api/assets/{relative_path}"


def write_text_artifact(kind: str, monitor_id: int, contents: str, suffix: str = ".txt") -> str:
    directory = settings.TEXT_DIR if kind != "html" else settings.HTML_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"monitor-{monitor_id}-{utc_stamp()}{suffix}"
    path.write_text(contents, encoding="utf-8")
    return relative_to_data(path)


def write_bytes_artifact(kind: str, monitor_id: int, contents: bytes, suffix: str = ".png") -> str:
    directory = settings.SCREENSHOT_DIR / kind
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"monitor-{monitor_id}-{utc_stamp()}{suffix}"
    path.write_bytes(contents)
    return relative_to_data(path)


def read_text_artifact(relative_path: str | None) -> str:
    path = data_path(relative_path)
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def from_json(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default

