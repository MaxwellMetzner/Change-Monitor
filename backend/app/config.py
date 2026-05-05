from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from .runtime_settings import RuntimeSettings, RuntimeSettingsStore, load_or_create_encryption_secret


class Settings:
    APP_NAME = "Change Monitor"
    DATA_DIR = Path(os.getenv("DATA_DIR", "./data")).resolve()

    def __init__(self) -> None:
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.DB_DIR.mkdir(parents=True, exist_ok=True)
        self.SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        self.TEXT_DIR.mkdir(parents=True, exist_ok=True)
        self.HTML_DIR.mkdir(parents=True, exist_ok=True)
        self.BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        self.LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.runtime_store = RuntimeSettingsStore(self.CONFIG_DIR)
        self.SECRET_KEY = load_or_create_encryption_secret(self.CONFIG_DIR)

    @property
    def CONFIG_DIR(self) -> Path:
        return self.DATA_DIR / "config"

    @property
    def RUNTIME_SETTINGS(self) -> RuntimeSettings:
        return self.runtime_store.current()

    @property
    def APP_BASE_URL(self) -> str:
        return self.RUNTIME_SETTINGS.app_base_url

    @property
    def DEFAULT_CHECK_INTERVAL_SECONDS(self) -> int:
        return self.RUNTIME_SETTINGS.default_check_interval_seconds

    @property
    def DEFAULT_JITTER_SECONDS(self) -> int:
        return self.RUNTIME_SETTINGS.default_jitter_seconds

    @property
    def DEFAULT_RENDER_WAIT_MS(self) -> int:
        return self.RUNTIME_SETTINGS.default_render_wait_ms

    @property
    def MAX_CONCURRENT_CHECKS(self) -> int:
        return self.RUNTIME_SETTINGS.max_concurrent_checks

    def update_runtime_settings(self, values: dict[str, object]) -> RuntimeSettings:
        return self.runtime_store.update(values)

    @property
    def DB_DIR(self) -> Path:
        return self.DATA_DIR / "db"

    @property
    def SCREENSHOT_DIR(self) -> Path:
        return self.DATA_DIR / "screenshots"

    @property
    def TEXT_DIR(self) -> Path:
        return self.DATA_DIR / "text"

    @property
    def HTML_DIR(self) -> Path:
        return self.DATA_DIR / "html"

    @property
    def BROWSER_PROFILE_DIR(self) -> Path:
        return self.DATA_DIR / "browser-profiles"

    @property
    def LOG_DIR(self) -> Path:
        return self.DATA_DIR / "logs"

    @property
    def DATABASE_URL(self) -> str:
        return f"sqlite:///{(self.DB_DIR / 'change_monitor.sqlite3').as_posix()}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
