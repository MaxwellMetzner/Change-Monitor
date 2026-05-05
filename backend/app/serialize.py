from __future__ import annotations

from sqlalchemy.orm import Session

from .models import Alert, CheckRun, Monitor, Rule, Snapshot
from .schemas import AlertRead, CheckRunRead, MonitorRead, RuleRead, SnapshotRead
from .storage import asset_url, from_json, read_text_artifact


def serialize_rule(rule: Rule) -> RuleRead:
    return RuleRead(
        id=rule.id,
        type=rule.type,
        config=from_json(rule.config_json, {}),
        enabled=rule.enabled,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


def serialize_snapshot(snapshot: Snapshot, *, include_text: bool = False) -> SnapshotRead:
    return SnapshotRead(
        id=snapshot.id,
        monitor_id=snapshot.monitor_id,
        created_at=snapshot.created_at,
        final_url=snapshot.final_url,
        page_title=snapshot.page_title,
        http_status=snapshot.http_status,
        raw_text=read_text_artifact(snapshot.raw_text_path) if include_text else None,
        normalized_text=read_text_artifact(snapshot.normalized_text_path) if include_text else None,
        screenshot_url=asset_url(snapshot.screenshot_path),
        element_screenshot_url=asset_url(snapshot.element_screenshot_path),
        text_hash=snapshot.text_hash,
        visual_hash=snapshot.visual_hash,
        metadata=from_json(snapshot.metadata_json, {}),
    )


def serialize_monitor(db: Session, monitor: Monitor, *, include_text: bool = False) -> MonitorRead:
    baseline = db.get(Snapshot, monitor.baseline_snapshot_id) if monitor.baseline_snapshot_id else None
    latest = (
        db.query(Snapshot)
        .filter(Snapshot.monitor_id == monitor.id)
        .order_by(Snapshot.created_at.desc())
        .first()
    )
    return MonitorRead(
        id=monitor.id,
        name=monitor.name,
        url=monitor.url,
        enabled=monitor.enabled,
        mode=monitor.mode,
        selector=monitor.selector,
        baseline_snapshot_id=monitor.baseline_snapshot_id,
        interval_seconds=monitor.interval_seconds,
        jitter_seconds=monitor.jitter_seconds,
        render_wait_ms=monitor.render_wait_ms,
        cooldown_seconds=monitor.cooldown_seconds,
        pushover_profile_id=monitor.pushover_profile_id,
        priority=monitor.priority,
        pause_after_alert=monitor.pause_after_alert,
        status=monitor.status,
        failure_count=monitor.failure_count,
        created_at=monitor.created_at,
        updated_at=monitor.updated_at,
        last_checked_at=monitor.last_checked_at,
        last_changed_at=monitor.last_changed_at,
        last_alerted_at=monitor.last_alerted_at,
        rules=[serialize_rule(rule) for rule in monitor.rules],
        baseline=serialize_snapshot(baseline, include_text=include_text) if baseline else None,
        latest_snapshot=serialize_snapshot(latest, include_text=include_text) if latest else None,
    )


def serialize_check_run(run: CheckRun) -> CheckRunRead:
    return CheckRunRead(
        id=run.id,
        monitor_id=run.monitor_id,
        started_at=run.started_at,
        finished_at=run.finished_at,
        status=run.status,
        change_score=run.change_score,
        triggered_rules=from_json(run.triggered_rules_json, []),
        error_message=run.error_message,
        snapshot_id=run.snapshot_id,
        alert_id=run.alert_id,
    )


def serialize_alert(alert: Alert) -> AlertRead:
    return AlertRead(
        id=alert.id,
        monitor_id=alert.monitor_id,
        check_run_id=alert.check_run_id,
        created_at=alert.created_at,
        status=alert.status,
        title=alert.title,
        message=alert.message,
        url=alert.url,
        retry_count=alert.retry_count,
        deduplication_key=alert.deduplication_key,
    )
