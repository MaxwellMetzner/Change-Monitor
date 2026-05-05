# Change Monitor

A self-hosted web app for monitoring rendered web pages and sending Pushover alerts when meaningful changes appear. The MVP focuses on retail/restock monitoring where the current state is known to be bad, such as "Out of Stock", but the future good state is unknown.

## What Is Implemented

- FastAPI backend with SQLite persistence.
- React, TypeScript, Vite, and Tailwind frontend.
- Playwright Chromium page rendering.
- Screenshot-based preview with clickable element overlays.
- Whole-page text, selected-element text, selected-element visual, and bad-state monitors.
- Baseline snapshots with stored text, HTML snippets, screenshots, and perceptual hashes.
- Rule evaluation for bad text disappearance, positive phrase appearance, text changes, selector loss, and visual hash changes.
- Manual check-now, pause/resume, delete, and rebaseline actions.
- Scheduler with jitter, low concurrency, per-domain locking, and failure backoff.
- Pushover profiles with encrypted local token storage.
- Alert records, cooldown deduplication, check run history, and Docker Compose deployment.

## Local Development

Backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
$env:DATA_DIR="..\data"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The Vite server proxies `/api` to `http://127.0.0.1:8000`.

## Docker

```powershell
copy .env.example .env
docker compose up --build
```

The app will be available at `http://localhost:8080`.

Persistent data is written to `./data`:

- `data/db`
- `data/screenshots`
- `data/text`
- `data/html`
- `data/browser-profiles`
- `data/logs`

## Configuration

Environment variables:

```text
APP_BASE_URL=http://localhost:8080
DATA_DIR=/data
DATABASE_URL=
SECRET_KEY=replace-this-with-a-long-random-value
DEFAULT_CHECK_INTERVAL_SECONDS=900
MAX_CONCURRENT_CHECKS=2
PLAYWRIGHT_BROWSERS_PATH=
LOG_LEVEL=INFO
PUSHOVER_DEFAULT_USER_KEY=
PUSHOVER_DEFAULT_APP_TOKEN=
AUTH_USERNAME=
AUTH_PASSWORD_HASH=
TZ=America/New_York
```

Authentication is intentionally left to a reverse proxy for this MVP. Put the service behind Tailscale, Caddy, Traefik, Authelia, or another trusted LAN-only access layer.

## Notes

- The app does not bypass CAPTCHAs, rotate proxies, automate purchasing, or perform checkout.
- Use conservative intervals. The default restock-oriented path uses 3 minutes with jitter.
- Screenshots can contain private page content. Keep the data volume protected and delete monitors you no longer need.

