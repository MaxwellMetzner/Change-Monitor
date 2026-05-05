from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from .browser import CaptureTarget, browser_service
from .comparator import DEFAULT_POSITIVE_PHRASES, evaluate_rules, extract_bad_phrase, unified_text_diff
from .models import Alert, CheckRun, Monitor, PushoverProfile, Rule, Snapshot, utc_now
from .notifier import send_pushover
from .storage import from_json, read_text_artifact, to_json


async def capture_and_store_snapshot(db: Session, monitor: Monitor, *, wait_ms: int | None = None) -> Snapshot:
    render_wait_ms = monitor.render_wait_ms if wait_ms is None else wait_ms
    capture = await browser_service.capture_snapshot(
        CaptureTarget(
            monitor_id=monitor.id,
            url=monitor.url,
            mode=monitor.mode,
            selector=monitor.selector,
            wait_ms=render_wait_ms,
        )
    )
    snapshot = Snapshot(
        monitor_id=monitor.id,
        final_url=capture.final_url,
        page_title=capture.page_title,
        http_status=capture.http_status,
        raw_text_path=capture.raw_text_path,
        normalized_text_path=capture.normalized_text_path,
        html_snippet_path=capture.html_snippet_path,
        screenshot_path=capture.screenshot_path,
        element_screenshot_path=capture.element_screenshot_path,
        text_hash=capture.text_hash,
        visual_hash=capture.visual_hash,
        metadata_json=to_json(capture.metadata),
    )
    db.add(snapshot)
    db.flush()
    return snapshot


def _rule_dicts(monitor: Monitor) -> list[dict[str, Any]]:
    return [
        {"type": rule.type, "config": from_json(rule.config_json, {}), "enabled": rule.enabled}
        for rule in monitor.rules
    ]


def add_default_rules(
    db: Session,
    monitor: Monitor,
    baseline_text: str,
    *,
    current_state_is_bad: bool,
    positive_phrases: list[str] | None,
    text_threshold: float,
) -> None:
    if current_state_is_bad:
        bad_phrase = extract_bad_phrase(baseline_text)
        db.add(
            Rule(
                monitor_id=monitor.id,
                type="bad_text_absent",
                config_json=to_json({"bad_text": bad_phrase or baseline_text.strip()[:240]}),
            )
        )
        db.add(
            Rule(
                monitor_id=monitor.id,
                type="positive_phrase_present",
                config_json=to_json({"phrases": positive_phrases or DEFAULT_POSITIVE_PHRASES}),
            )
        )
        if monitor.selector:
            db.add(
                Rule(
                    monitor_id=monitor.id,
                    type="any_visual_change",
                    config_json=to_json({"hamming_threshold": 18}),
                )
            )
        return

    db.add(
        Rule(
            monitor_id=monitor.id,
            type="any_text_change",
            config_json=to_json({"threshold": text_threshold, "minimum_changed_characters": 8}),
        )
    )


async def initialize_monitor(
    db: Session,
    monitor: Monitor,
    *,
    current_state_is_bad: bool,
    positive_phrases: list[str] | None,
    text_threshold: float,
    wait_ms: int,
) -> Monitor:
    snapshot = await capture_and_store_snapshot(db, monitor, wait_ms=wait_ms)
    monitor.baseline_snapshot_id = snapshot.id
    monitor.status = "ready"
    baseline_text = read_text_artifact(snapshot.raw_text_path)
    add_default_rules(
        db,
        monitor,
        baseline_text,
        current_state_is_bad=current_state_is_bad,
        positive_phrases=positive_phrases,
        text_threshold=text_threshold,
    )
    db.flush()
    return monitor


def _latest_snapshot(db: Session, monitor_id: int) -> Snapshot | None:
    return db.scalars(
        select(Snapshot).where(Snapshot.monitor_id == monitor_id).order_by(desc(Snapshot.created_at)).limit(1)
    ).first()


def _snapshot_text(snapshot: Snapshot | None) -> str:
    if snapshot is None:
        return ""
    return read_text_artifact(snapshot.raw_text_path)


def _selector_found(snapshot: Snapshot) -> bool:
    metadata = from_json(snapshot.metadata_json, {})
    return bool(metadata.get("selector_found", True))


def _visual_hash_family(value: str | None) -> str:
    if not value:
        return ""
    if ":" not in value:
        return "legacy-ahash"
    return value.split(":", 1)[0]


def _dedup_key(monitor_id: int, triggered_rules: list[dict[str, Any]], state_hash: str) -> str:
    rule_names = ",".join(sorted({str(rule.get("type")) for rule in triggered_rules}))
    return f"{monitor_id}:{rule_names}:{state_hash[:32]}"


def _recent_duplicate(db: Session, monitor: Monitor, dedup_key: str) -> Alert | None:
    cutoff = utc_now() - timedelta(seconds=monitor.cooldown_seconds)
    return db.scalars(
        select(Alert)
        .where(Alert.monitor_id == monitor.id)
        .where(Alert.deduplication_key == dedup_key)
        .where(Alert.created_at >= cutoff)
        .order_by(desc(Alert.created_at))
        .limit(1)
    ).first()


async def _create_alert_if_needed(
    db: Session,
    *,
    monitor: Monitor,
    run: CheckRun,
    evaluation,
) -> Alert | None:
    dedup_key = _dedup_key(monitor.id, evaluation.triggered_rules, evaluation.deduplication_state)
    duplicate = _recent_duplicate(db, monitor, dedup_key)
    title = monitor.name
    message = evaluation.summary[:900]
    alert = Alert(
        monitor_id=monitor.id,
        check_run_id=run.id,
        title=title,
        message=message,
        url=monitor.url,
        status="pending",
        deduplication_key=dedup_key,
    )
    db.add(alert)
    db.flush()

    if duplicate is not None:
        alert.status = "suppressed"
        alert.pushover_response = f"Duplicate suppressed during {monitor.cooldown_seconds}s cooldown."
        return alert

    profile: PushoverProfile | None = monitor.pushover_profile
    if profile is None:
        alert.status = "suppressed"
        alert.pushover_response = "No Pushover profile configured."
        return alert

    result = await send_pushover(profile, title=title, message=message, url=monitor.url, priority=monitor.priority)
    alert.status = result.status
    alert.pushover_response = result.response
    if result.status == "sent":
        monitor.last_alerted_at = utc_now()
    return alert


async def run_monitor_check(db: Session, monitor_id: int, *, manual: bool = False) -> CheckRun:
    monitor = db.get(Monitor, monitor_id)
    if monitor is None:
        raise ValueError("Monitor not found")

    run = CheckRun(monitor_id=monitor.id, started_at=utc_now(), status="running")
    db.add(run)
    db.flush()
    try:
        snapshot = await capture_and_store_snapshot(db, monitor)
        run.snapshot_id = snapshot.id
        monitor.last_checked_at = utc_now()

        baseline = db.get(Snapshot, monitor.baseline_snapshot_id) if monitor.baseline_snapshot_id else None
        if baseline is None:
            monitor.baseline_snapshot_id = snapshot.id
            monitor.status = "ready"
            run.status = "unchanged"
            run.finished_at = utc_now()
            db.commit()
            return run

        old_text = _snapshot_text(baseline)
        new_text = _snapshot_text(snapshot)
        if (
            baseline.visual_hash
            and snapshot.visual_hash
            and _visual_hash_family(baseline.visual_hash) != _visual_hash_family(snapshot.visual_hash)
            and baseline.text_hash == snapshot.text_hash
        ):
            baseline.visual_hash = snapshot.visual_hash
        evaluation = evaluate_rules(
            old_text=old_text,
            new_text=new_text,
            old_visual_hash=baseline.visual_hash,
            new_visual_hash=snapshot.visual_hash,
            rules=_rule_dicts(monitor),
            selector_found=_selector_found(snapshot),
        )
        run.change_score = evaluation.change_score
        run.triggered_rules_json = to_json(evaluation.triggered_rules)
        monitor.failure_count = 0

        if evaluation.alert:
            alert = await _create_alert_if_needed(db, monitor=monitor, run=run, evaluation=evaluation)
            run.alert_id = alert.id if alert else None
            run.status = "alert_sent" if alert and alert.status == "sent" else "changed"
            monitor.status = run.status
            monitor.last_changed_at = utc_now()
            if monitor.pause_after_alert and alert and alert.status == "sent":
                monitor.enabled = False
                monitor.status = "paused_after_alert"
        elif evaluation.changed:
            run.status = "changed"
            monitor.status = "changed"
            monitor.last_changed_at = utc_now()
        else:
            run.status = "unchanged"
            monitor.status = "ready"

        run.finished_at = utc_now()
        db.commit()
        return run
    except Exception as exc:
        monitor.failure_count += 1
        monitor.last_checked_at = utc_now()
        monitor.status = "failed"
        run.status = "failed"
        run.error_message = str(exc)
        run.finished_at = utc_now()
        db.commit()
        return run


async def rebaseline_monitor(db: Session, monitor_id: int) -> Snapshot:
    monitor = db.get(Monitor, monitor_id)
    if monitor is None:
        raise ValueError("Monitor not found")
    snapshot = await capture_and_store_snapshot(db, monitor)
    monitor.baseline_snapshot_id = snapshot.id
    monitor.status = "ready"
    monitor.updated_at = utc_now()
    db.commit()
    return snapshot


def diff_snapshots(from_snapshot: Snapshot, to_snapshot: Snapshot) -> str:
    return unified_text_diff(_snapshot_text(from_snapshot), _snapshot_text(to_snapshot))


def latest_snapshot(db: Session, monitor_id: int) -> Snapshot | None:
    return _latest_snapshot(db, monitor_id)
