from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return int(raw)


class Settings:
    APP_NAME = "Change Monitor"
    APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")
    DATA_DIR = Path(os.getenv("DATA_DIR", "./data")).resolve()
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
    DEFAULT_CHECK_INTERVAL_SECONDS = _env_int("DEFAULT_CHECK_INTERVAL_SECONDS", 900)
    MAX_CONCURRENT_CHECKS = _env_int("MAX_CONCURRENT_CHECKS", 2)
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    PLAYWRIGHT_BROWSERS_PATH = os.getenv("PLAYWRIGHT_BROWSERS_PATH")
    AUTH_USERNAME = os.getenv("AUTH_USERNAME")
    AUTH_PASSWORD_HASH = os.getenv("AUTH_PASSWORD_HASH")
    PUSHOVER_DEFAULT_USER_KEY = os.getenv("PUSHOVER_DEFAULT_USER_KEY")
    PUSHOVER_DEFAULT_APP_TOKEN = os.getenv("PUSHOVER_DEFAULT_APP_TOKEN")

    def __init__(self) -> None:
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.DB_DIR.mkdir(parents=True, exist_ok=True)
        self.SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        self.TEXT_DIR.mkdir(parents=True, exist_ok=True)
        self.HTML_DIR.mkdir(parents=True, exist_ok=True)
        self.BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        self.LOG_DIR.mkdir(parents=True, exist_ok=True)

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
        configured = os.getenv("DATABASE_URL")
        if configured:
            return configured
        return f"sqlite:///{(self.DB_DIR / 'change_monitor.sqlite3').as_posix()}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

