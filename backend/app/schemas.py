from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, HttpUrl, field_validator


MonitorMode = Literal["whole_page_text", "element_text", "element_visual", "bad_state"]


class RuleConfig(BaseModel):
    type: str
    config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class MonitorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    url: HttpUrl
    mode: MonitorMode = "bad_state"
    selector: str | None = None
    interval_seconds: int | None = Field(default=None, ge=10, le=86_400)
    jitter_seconds: int | None = Field(default=None, ge=0)
    render_wait_ms: int | None = Field(default=None, ge=0, le=15000)
    cooldown_seconds: int = Field(default=1800, ge=0)
    pushover_profile_id: int | None = None
    priority: int = 0
    pause_after_alert: bool = False
    current_state_is_bad: bool = True
    positive_phrases: list[str] | None = None
    text_threshold: float = Field(default=0.12, ge=0.0, le=1.0)
    wait_ms: int = Field(default=1500, ge=0, le=15000)


class MonitorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    url: HttpUrl | None = None
    enabled: bool | None = None
    mode: MonitorMode | None = None
    selector: str | None = None
    interval_seconds: int | None = Field(default=None, ge=10, le=86_400)
    jitter_seconds: int | None = Field(default=None, ge=0)
    render_wait_ms: int | None = Field(default=None, ge=0, le=15000)
    cooldown_seconds: int | None = Field(default=None, ge=0)
    pushover_profile_id: int | None = None
    priority: int | None = None
    pause_after_alert: bool | None = None


class RuleRead(BaseModel):
    id: int
    type: str
    config: dict[str, Any]
    enabled: bool
    created_at: datetime
    updated_at: datetime


class SnapshotRead(BaseModel):
    id: int
    monitor_id: int
    created_at: datetime
    final_url: str | None
    page_title: str | None
    http_status: int | None
    raw_text: str | None = None
    normalized_text: str | None = None
    screenshot_url: str | None = None
    element_screenshot_url: str | None = None
    text_hash: str | None
    visual_hash: str | None
    metadata: dict[str, Any]


class MonitorRead(BaseModel):
    id: int
    name: str
    url: str
    enabled: bool
    mode: str
    selector: str | None
    baseline_snapshot_id: int | None
    interval_seconds: int
    jitter_seconds: int
    render_wait_ms: int
    cooldown_seconds: int
    pushover_profile_id: int | None
    priority: int
    pause_after_alert: bool
    status: str
    failure_count: int
    created_at: datetime
    updated_at: datetime
    last_checked_at: datetime | None
    last_changed_at: datetime | None
    last_alerted_at: datetime | None
    rules: list[RuleRead] = Field(default_factory=list)
    baseline: SnapshotRead | None = None
    latest_snapshot: SnapshotRead | None = None


class CheckRunRead(BaseModel):
    id: int
    monitor_id: int
    started_at: datetime
    finished_at: datetime | None
    status: str
    change_score: float
    triggered_rules: list[dict[str, Any]]
    error_message: str | None
    snapshot_id: int | None
    alert_id: int | None


class AlertRead(BaseModel):
    id: int
    monitor_id: int
    check_run_id: int | None
    created_at: datetime
    status: str
    title: str
    message: str
    url: str | None
    retry_count: int
    deduplication_key: str


class PreviewLoadRequest(BaseModel):
    url: HttpUrl
    wait_ms: int = Field(default=1500, ge=0, le=15000)
    viewport_width: int = Field(default=1440, ge=320, le=2560)
    viewport_height: int = Field(default=1200, ge=320, le=3000)


class PreviewElement(BaseModel):
    selector: str
    tag: str
    label: str
    text: str
    rect: dict[str, float]
    match_count: int
    selector_quality: str


class PreviewLoadResponse(BaseModel):
    url: str
    final_url: str | None
    page_title: str | None
    http_status: int | None
    screenshot_base64: str
    screenshot_width: int
    screenshot_height: int
    elements: list[PreviewElement]
    captured_text: str


class PreviewSelectRequest(BaseModel):
    url: HttpUrl
    selector: str
    wait_ms: int = Field(default=1500, ge=0, le=15000)


class PreviewSelectionResponse(BaseModel):
    selector: str
    text: str
    html: str
    match_count: int
    rect: dict[str, float] | None
    screenshot_base64: str | None = None


class PushoverProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    user_key: str = Field(min_length=1)
    app_token: str = Field(min_length=1)
    default_device: str | None = None
    devices: list[str] = Field(default_factory=list)
    default_priority: int = 0


class PushoverProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    default_device: str | None = None
    devices: list[str] | None = None
    default_priority: int | None = None


class PushoverProfileValidateRequest(BaseModel):
    user_key: str = Field(min_length=1)
    app_token: str = Field(min_length=1)


class PushoverProfileValidateResponse(BaseModel):
    status: str
    devices: list[str]
    response: str


class PushoverProfileRead(BaseModel):
    id: int
    name: str
    default_device: str | None
    devices: list[str]
    default_priority: int
    created_at: datetime
    updated_at: datetime


class TestAlertRequest(BaseModel):
    title: str = "Change Monitor test"
    message: str = "Pushover is connected."


class DiffResponse(BaseModel):
    from_snapshot_id: int
    to_snapshot_id: int
    from_text: str
    to_text: str
    unified_diff: str


class AppSettingsRead(BaseModel):
    app_base_url: str
    default_check_interval_seconds: int
    default_jitter_seconds: int
    default_render_wait_ms: int
    max_concurrent_checks: int
    data_dir: str
    settings_path: str
    settings_hash: str
    settings_hash_valid: bool | None
    encryption_key_status: str


class AppSettingsUpdate(BaseModel):
    app_base_url: str | None = Field(default=None, max_length=500)
    default_check_interval_seconds: int | None = Field(default=None, ge=60, le=86_400)
    default_jitter_seconds: int | None = Field(default=None, ge=0, le=3_600)
    default_render_wait_ms: int | None = Field(default=None, ge=0, le=15_000)
    max_concurrent_checks: int | None = Field(default=None, ge=1, le=8)

    @field_validator("app_base_url")
    @classmethod
    def validate_app_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return value
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("App URL must be a full http:// or https:// URL.")
        return value.rstrip("/")
