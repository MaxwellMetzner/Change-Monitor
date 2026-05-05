from __future__ import annotations

import hashlib
import json
import os
import secrets
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


class RuntimeSettings(BaseModel):
    app_base_url: str = Field(default="http://localhost:8000", max_length=500)
    default_check_interval_seconds: int = Field(default=180, ge=60, le=86_400)
    default_jitter_seconds: int = Field(default=20, ge=0, le=3_600)
    default_render_wait_ms: int = Field(default=1500, ge=0, le=15_000)
    max_concurrent_checks: int = Field(default=2, ge=1, le=8)

    @field_validator("app_base_url")
    @classmethod
    def validate_app_base_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("App URL must be a full http:// or https:// URL.")
        return value.rstrip("/")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def settings_hash(values: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(values).encode("utf-8")).hexdigest()


def load_or_create_encryption_secret(config_dir: Path) -> str:
    config_dir.mkdir(parents=True, exist_ok=True)
    key_path = config_dir / "encryption.key"
    if key_path.exists():
        existing = key_path.read_text(encoding="utf-8").strip()
        if existing:
            return existing

    seed = os.getenv("CHANGE_MONITOR_SECRET_KEY") or os.getenv("SECRET_KEY")
    secret = seed.strip() if seed else secrets.token_urlsafe(48)
    key_path.write_text(secret + "\n", encoding="utf-8")
    try:
        key_path.chmod(0o600)
    except OSError:
        pass
    return secret


class RuntimeSettingsStore:
    def __init__(self, config_dir: Path) -> None:
        self.config_dir = config_dir
        self.path = config_dir / "app-settings.json"
        self.last_hash_valid: bool | None = None
        self._current = self._load()

    def current(self) -> RuntimeSettings:
        return self._current

    def update(self, values: dict[str, Any]) -> RuntimeSettings:
        clean_values = {key: value for key, value in values.items() if value is not None}
        next_settings = RuntimeSettings.model_validate({**self._current.model_dump(), **clean_values})
        self._save(next_settings)
        self._current = next_settings
        self.last_hash_valid = True
        return next_settings

    @property
    def current_hash(self) -> str:
        return settings_hash(self._current.model_dump())

    def _load(self) -> RuntimeSettings:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            settings = RuntimeSettings()
            self._save(settings)
            self.last_hash_valid = True
            return settings

        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            values = raw.get("values", raw)
            stored_hash = raw.get("integrity_hash")
            actual_hash = settings_hash(values)
            self.last_hash_valid = stored_hash == actual_hash if stored_hash else None
            settings = RuntimeSettings.model_validate(values)
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            settings = RuntimeSettings()
            self.last_hash_valid = False

        if self.last_hash_valid is not True:
            self._save(settings)
            self.last_hash_valid = True
        return settings

    def _save(self, settings: RuntimeSettings) -> None:
        values = settings.model_dump()
        payload = {
            "version": 1,
            "values": values,
            "integrity_hash": settings_hash(values),
        }
        temp_path = self.path.with_suffix(".json.tmp")
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temp_path.replace(self.path)
        try:
            self.path.chmod(0o600)
        except OSError:
            pass
