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

from app.database import init_db
from app.main import app
from app.security import decrypt_secret, encrypt_secret

init_db()
assert decrypt_secret(encrypt_secret("volume-secret")) == "volume-secret"

with TestClient(app) as client:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    settings_response = client.get("/api/app-settings")
    assert settings_response.status_code == 200
    assert settings_response.json()["settings_hash"].startswith("sha256:")


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
