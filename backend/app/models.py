from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Monitor(Base):
    __tablename__ = "monitors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    mode: Mapped[str] = mapped_column(String(50), default="element_text", nullable=False)
    selector: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    region_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    baseline_snapshot_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    interval_seconds: Mapped[int] = mapped_column(Integer, default=900, nullable=False)
    jitter_seconds: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    render_wait_ms: Mapped[int] = mapped_column(Integer, default=1500, nullable=False)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=1800, nullable=False)
    pushover_profile_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("pushover_profiles.id"), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pause_after_alert: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="new", nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_alerted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    snapshots: Mapped[list["Snapshot"]] = relationship(back_populates="monitor", cascade="all, delete-orphan")
    rules: Mapped[list["Rule"]] = relationship(back_populates="monitor", cascade="all, delete-orphan")
    check_runs: Mapped[list["CheckRun"]] = relationship(back_populates="monitor", cascade="all, delete-orphan")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="monitor", cascade="all, delete-orphan")
    pushover_profile: Mapped[Optional["PushoverProfile"]] = relationship(back_populates="monitors")


class Snapshot(Base):
    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    monitor_id: Mapped[int] = mapped_column(Integer, ForeignKey("monitors.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    final_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    page_title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    http_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    raw_text_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    normalized_text_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    html_snippet_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    screenshot_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    element_screenshot_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    text_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    visual_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    monitor: Mapped[Monitor] = relationship(back_populates="snapshots")


class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    monitor_id: Mapped[int] = mapped_column(Integer, ForeignKey("monitors.id", ondelete="CASCADE"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(80), nullable=False)
    config_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    monitor: Mapped[Monitor] = relationship(back_populates="rules")


class CheckRun(Base):
    __tablename__ = "check_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    monitor_id: Mapped[int] = mapped_column(Integer, ForeignKey("monitors.id", ondelete="CASCADE"), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(60), default="running", nullable=False)
    change_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    triggered_rules_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    snapshot_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("snapshots.id"), nullable=True)
    alert_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("alerts.id"), nullable=True)

    monitor: Mapped[Monitor] = relationship(back_populates="check_runs")
    snapshot: Mapped[Optional[Snapshot]] = relationship(foreign_keys=[snapshot_id])


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    monitor_id: Mapped[int] = mapped_column(Integer, ForeignKey("monitors.id", ondelete="CASCADE"), nullable=False, index=True)
    check_run_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("check_runs.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    status: Mapped[str] = mapped_column(String(60), default="pending", nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pushover_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    deduplication_key: Mapped[str] = mapped_column(String(200), nullable=False, index=True)

    monitor: Mapped[Monitor] = relationship(back_populates="alerts")


class PushoverProfile(Base):
    __tablename__ = "pushover_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    user_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    app_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    default_device: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    default_priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    monitors: Mapped[list[Monitor]] = relationship(back_populates="pushover_profile")
