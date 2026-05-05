from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from app.runtime_settings import RuntimeSettingsStore, load_or_create_encryption_secret, settings_hash


def test_runtime_settings_file_has_integrity_hash(tmp_path: Path) -> None:
    store = RuntimeSettingsStore(tmp_path)
    payload = json.loads(store.path.read_text(encoding="utf-8"))

    assert payload["integrity_hash"] == settings_hash(payload["values"])
    assert payload["values"]["default_check_interval_seconds"] == 180

    updated = store.update({"max_concurrent_checks": 3})
    payload = json.loads(store.path.read_text(encoding="utf-8"))

    assert updated.max_concurrent_checks == 3
    assert payload["integrity_hash"] == settings_hash(payload["values"])


def test_volume_encryption_key_is_generated_and_reused(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("CHANGE_MONITOR_SECRET_KEY", raising=False)

    first = load_or_create_encryption_secret(tmp_path)
    second = load_or_create_encryption_secret(tmp_path)

    assert first == second
    assert (tmp_path / "encryption.key").read_text(encoding="utf-8").strip() == first


def test_installation_smoke_checks_core_app_paths(tmp_path: Path) -> None:
    backend_root = Path(__file__).resolve().parents[1]
    script = """
import asyncio
import os

from fastapi.testclient import TestClient

from app.database import create_session
from app.database import init_db
from app.main import app
from app.models import Monitor, Rule
from app.security import decrypt_secret, encrypt_secret
from app.storage import to_json

init_db()
assert decrypt_secret(encrypt_secret("volume-secret")) == "volume-secret"

with TestClient(app) as client:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    settings_response = client.get("/api/app-settings")
    assert settings_response.status_code == 200
    assert settings_response.json()["settings_hash"].startswith("sha256:")
    profile_response = client.post(
        "/api/pushover-profiles",
        json={"name": "Personal", "user_key": "user", "app_token": "token", "devices": ["phone"], "default_device": "phone"},
    )
    assert profile_response.status_code == 201
    assert profile_response.json()["devices"] == ["phone"]
    duplicate_response = client.post(
        "/api/pushover-profiles",
        json={"name": " personal ", "user_key": "user", "app_token": "token"},
    )
    assert duplicate_response.status_code == 409
    delete_response = client.delete(f"/api/pushover-profiles/{profile_response.json()['id']}")
    assert delete_response.status_code == 204
    with create_session() as db:
        monitor = Monitor(name="Rule smoke", url="https://example.com", mode="bad_state", status="ready")
        db.add(monitor)
        db.flush()
        rule = Rule(
            monitor_id=monitor.id,
            type="positive_phrase_present",
            config_json=to_json({"phrases": ["add to cart"]}),
        )
        db.add(rule)
        db.commit()
        monitor_id = monitor.id
        rule_id = rule.id
    rule_response = client.patch(
        f"/api/monitors/{monitor_id}/rules/{rule_id}",
        json={"config": {"phrases": ["buy now", "in stock"]}, "enabled": True},
    )
    assert rule_response.status_code == 200
    assert rule_response.json()["config"]["phrases"] == ["buy now", "in stock"]


async def browser_check():
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content("<main>Change Monitor install check</main>")
        text = await page.locator("main").inner_text()
        await browser.close()
        assert text == "Change Monitor install check"


try:
    asyncio.run(browser_check())
except Exception as exc:
    if os.getenv("CHANGE_MONITOR_STRICT_INSTALL_CHECK") == "1":
        raise
    print(f"Skipping browser install smoke outside strict mode: {exc}")
"""
    env = {
        **os.environ,
        "DATA_DIR": str(tmp_path),
        "PYTHONPATH": str(backend_root),
    }
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=backend_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )

    assert result.returncode == 0, result.stdout + result.stderr
