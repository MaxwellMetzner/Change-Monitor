from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from .browser import browser_service
from .config import settings
from .database import get_db, init_db
from .models import Alert, CheckRun, Monitor, PushoverProfile, Snapshot
from .notifier import send_pushover
from .schemas import (
    AlertRead,
    AppSettingsRead,
    AppSettingsUpdate,
    CheckRunRead,
    DiffResponse,
    MonitorCreate,
    MonitorRead,
    MonitorUpdate,
    PreviewLoadRequest,
    PreviewLoadResponse,
    PreviewSelectRequest,
    PreviewSelectionResponse,
    PushoverProfileCreate,
    PushoverProfileRead,
    SnapshotRead,
    TestAlertRequest,
)
from .scheduler import scheduler
from .security import encrypt_secret
from .serialize import serialize_alert, serialize_check_run, serialize_monitor, serialize_snapshot
from .services import diff_snapshots, initialize_monitor, rebaseline_monitor, run_monitor_check
from .storage import read_text_artifact


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    scheduler.start()
    try:
        yield
    finally:
        await scheduler.stop()
        await browser_service.stop()


app = FastAPI(title=settings.APP_NAME, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", settings.APP_BASE_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/api/assets", StaticFiles(directory=str(settings.DATA_DIR)), name="assets")


Db = Annotated[Session, Depends(get_db)]


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health", include_in_schema=False)
def container_health() -> dict[str, str]:
    return health()


def _app_settings_response() -> AppSettingsRead:
    runtime = settings.RUNTIME_SETTINGS
    return AppSettingsRead(
        app_base_url=runtime.app_base_url,
        default_check_interval_seconds=runtime.default_check_interval_seconds,
        default_jitter_seconds=runtime.default_jitter_seconds,
        default_render_wait_ms=runtime.default_render_wait_ms,
        max_concurrent_checks=runtime.max_concurrent_checks,
        data_dir=str(settings.DATA_DIR),
        settings_path=str(settings.runtime_store.path),
        settings_hash=settings.runtime_store.current_hash,
        settings_hash_valid=settings.runtime_store.last_hash_valid,
        encryption_key_status="stored in data volume",
    )


@app.get("/api/app-settings", response_model=AppSettingsRead)
def get_app_settings() -> AppSettingsRead:
    return _app_settings_response()


@app.patch("/api/app-settings", response_model=AppSettingsRead)
def update_app_settings(payload: AppSettingsUpdate) -> AppSettingsRead:
    settings.update_runtime_settings(payload.model_dump(exclude_unset=True))
    scheduler.configure(max_concurrent_checks=settings.MAX_CONCURRENT_CHECKS)
    return _app_settings_response()


@app.get("/api/monitors", response_model=list[MonitorRead])
def list_monitors(db: Db) -> list[MonitorRead]:
    monitors = db.scalars(select(Monitor).order_by(desc(Monitor.created_at))).all()
    return [serialize_monitor(db, monitor) for monitor in monitors]


@app.post("/api/monitors", response_model=MonitorRead, status_code=status.HTTP_201_CREATED)
async def create_monitor(payload: MonitorCreate, db: Db) -> MonitorRead:
    monitor = Monitor(
        name=payload.name,
        url=str(payload.url),
        mode=payload.mode,
        selector=payload.selector,
        interval_seconds=payload.interval_seconds or settings.DEFAULT_CHECK_INTERVAL_SECONDS,
        jitter_seconds=payload.jitter_seconds if payload.jitter_seconds is not None else settings.DEFAULT_JITTER_SECONDS,
        render_wait_ms=payload.render_wait_ms or payload.wait_ms or settings.DEFAULT_RENDER_WAIT_MS,
        cooldown_seconds=payload.cooldown_seconds,
        pushover_profile_id=payload.pushover_profile_id,
        priority=payload.priority,
        pause_after_alert=payload.pause_after_alert,
        enabled=True,
        status="capturing_baseline",
    )
    db.add(monitor)
    try:
        db.flush()
        await initialize_monitor(
            db,
            monitor,
            current_state_is_bad=payload.current_state_is_bad,
            positive_phrases=payload.positive_phrases,
            text_threshold=payload.text_threshold,
            wait_ms=payload.wait_ms,
        )
        db.commit()
        db.refresh(monitor)
        return serialize_monitor(db, monitor, include_text=True)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"Baseline capture failed: {exc}") from exc


@app.get("/api/monitors/{monitor_id}", response_model=MonitorRead)
def get_monitor(monitor_id: int, db: Db) -> MonitorRead:
    monitor = db.get(Monitor, monitor_id)
    if monitor is None:
        raise HTTPException(status_code=404, detail="Monitor not found")
    return serialize_monitor(db, monitor, include_text=True)


@app.patch("/api/monitors/{monitor_id}", response_model=MonitorRead)
def update_monitor(monitor_id: int, payload: MonitorUpdate, db: Db) -> MonitorRead:
    monitor = db.get(Monitor, monitor_id)
    if monitor is None:
        raise HTTPException(status_code=404, detail="Monitor not found")
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(monitor, field, str(value) if field == "url" and value is not None else value)
    db.commit()
    db.refresh(monitor)
    return serialize_monitor(db, monitor, include_text=True)


@app.delete("/api/monitors/{monitor_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_monitor(monitor_id: int, db: Db) -> Response:
    monitor = db.get(Monitor, monitor_id)
    if monitor is None:
        raise HTTPException(status_code=404, detail="Monitor not found")
    db.delete(monitor)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/api/monitors/{monitor_id}/check-now", response_model=CheckRunRead)
async def check_now(monitor_id: int, db: Db) -> CheckRunRead:
    if db.get(Monitor, monitor_id) is None:
        raise HTTPException(status_code=404, detail="Monitor not found")
    run = await run_monitor_check(db, monitor_id, manual=True)
    return serialize_check_run(run)


@app.post("/api/monitors/{monitor_id}/pause", response_model=MonitorRead)
def pause_monitor(monitor_id: int, db: Db) -> MonitorRead:
    monitor = db.get(Monitor, monitor_id)
    if monitor is None:
        raise HTTPException(status_code=404, detail="Monitor not found")
    monitor.enabled = False
    monitor.status = "paused"
    db.commit()
    return serialize_monitor(db, monitor)


@app.post("/api/monitors/{monitor_id}/resume", response_model=MonitorRead)
def resume_monitor(monitor_id: int, db: Db) -> MonitorRead:
    monitor = db.get(Monitor, monitor_id)
    if monitor is None:
        raise HTTPException(status_code=404, detail="Monitor not found")
    monitor.enabled = True
    monitor.status = "ready"
    db.commit()
    return serialize_monitor(db, monitor)


@app.post("/api/monitors/{monitor_id}/rebaseline", response_model=SnapshotRead)
async def rebaseline(monitor_id: int, db: Db) -> SnapshotRead:
    try:
        snapshot = await rebaseline_monitor(db, monitor_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return serialize_snapshot(snapshot, include_text=True)


@app.get("/api/monitors/{monitor_id}/runs", response_model=list[CheckRunRead])
def monitor_runs(monitor_id: int, db: Db, limit: int = Query(default=50, ge=1, le=200)) -> list[CheckRunRead]:
    runs = db.scalars(
        select(CheckRun).where(CheckRun.monitor_id == monitor_id).order_by(desc(CheckRun.started_at)).limit(limit)
    ).all()
    return [serialize_check_run(run) for run in runs]


@app.get("/api/monitors/{monitor_id}/snapshots/{snapshot_id}", response_model=SnapshotRead)
def get_snapshot(monitor_id: int, snapshot_id: int, db: Db) -> SnapshotRead:
    snapshot = db.get(Snapshot, snapshot_id)
    if snapshot is None or snapshot.monitor_id != monitor_id:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return serialize_snapshot(snapshot, include_text=True)


@app.get("/api/monitors/{monitor_id}/diff", response_model=DiffResponse)
def get_diff(
    monitor_id: int,
    db: Db,
    from_snapshot_id: int = Query(alias="from"),
    to_snapshot_id: int = Query(alias="to"),
) -> DiffResponse:
    from_snapshot = db.get(Snapshot, from_snapshot_id)
    to_snapshot = db.get(Snapshot, to_snapshot_id)
    if (
        from_snapshot is None
        or to_snapshot is None
        or from_snapshot.monitor_id != monitor_id
        or to_snapshot.monitor_id != monitor_id
    ):
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return DiffResponse(
        from_snapshot_id=from_snapshot_id,
        to_snapshot_id=to_snapshot_id,
        from_text=read_text_artifact(from_snapshot.raw_text_path),
        to_text=read_text_artifact(to_snapshot.raw_text_path),
        unified_diff=diff_snapshots(from_snapshot, to_snapshot),
    )


@app.post("/api/preview/load", response_model=PreviewLoadResponse)
async def preview_load(payload: PreviewLoadRequest) -> PreviewLoadResponse:
    try:
        return PreviewLoadResponse(
            **await browser_service.load_preview(
                str(payload.url),
                wait_ms=payload.wait_ms,
                viewport_width=payload.viewport_width,
                viewport_height=payload.viewport_height,
            )
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Preview capture failed: {exc}") from exc


@app.post("/api/preview/select-element", response_model=PreviewSelectionResponse)
async def preview_select(payload: PreviewSelectRequest) -> PreviewSelectionResponse:
    try:
        return PreviewSelectionResponse(**await browser_service.select_element(str(payload.url), payload.selector, wait_ms=payload.wait_ms))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Element selection failed: {exc}") from exc


@app.get("/api/pushover-profiles", response_model=list[PushoverProfileRead])
def list_pushover_profiles(db: Db) -> list[PushoverProfileRead]:
    profiles = db.scalars(select(PushoverProfile).order_by(PushoverProfile.name)).all()
    return [
        PushoverProfileRead(
            id=profile.id,
            name=profile.name,
            default_device=profile.default_device,
            default_priority=profile.default_priority,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )
        for profile in profiles
    ]


@app.post("/api/pushover-profiles", response_model=PushoverProfileRead, status_code=status.HTTP_201_CREATED)
def create_pushover_profile(payload: PushoverProfileCreate, db: Db) -> PushoverProfileRead:
    profile = PushoverProfile(
        name=payload.name,
        user_key_encrypted=encrypt_secret(payload.user_key),
        app_token_encrypted=encrypt_secret(payload.app_token),
        default_device=payload.default_device,
        default_priority=payload.default_priority,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return PushoverProfileRead(
        id=profile.id,
        name=profile.name,
        default_device=profile.default_device,
        default_priority=profile.default_priority,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@app.post("/api/pushover-profiles/{profile_id}/test")
async def test_pushover_profile(profile_id: int, payload: TestAlertRequest, db: Db) -> dict[str, str]:
    profile = db.get(PushoverProfile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Pushover profile not found")
    result = await send_pushover(profile, title=payload.title, message=payload.message)
    return {"status": result.status, "response": result.response}


@app.get("/api/alerts", response_model=list[AlertRead])
def list_alerts(db: Db, limit: int = Query(default=100, ge=1, le=500)) -> list[AlertRead]:
    alerts = db.scalars(select(Alert).order_by(desc(Alert.created_at)).limit(limit)).all()
    return [serialize_alert(alert) for alert in alerts]


frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
else:

    @app.get("/")
    def root() -> dict[str, str]:
        return {"message": "Change Monitor API is running. Build the frontend to serve the app from this process."}

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon() -> FileResponse:
        raise HTTPException(status_code=404, detail="No favicon")
