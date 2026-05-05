# Stock/Change Monitor App — Requirements Document

## 1. Product Summary

Build a self-hosted web app that monitors web pages for meaningful changes and sends alerts through Pushover. The primary use case is retail availability monitoring, such as detecting when a product changes from “Out of Stock” to any other state, even when the user does not know what the in-stock message will look like.

The app should support both simple users who want a guided “watch this product” workflow and advanced users who want CSS selectors, regex rules, visual comparisons, raw HTML checks, and notification tuning.

## 2. Primary Goals

1. Let users create monitors for a whole page, a selected element, or a selected visual region.
2. Detect changes in dynamic, JavaScript-rendered pages using a real browser engine.
3. Support “unknown target state” monitoring, where the user only knows the current bad state, such as “Out of Stock.”
4. Send fast, deduplicated Pushover alerts with the monitored URL and change summary.
5. Keep setup clean enough for non-technical use while still exposing advanced controls.
6. Run reliably as a Dockerized service on a home server.

## 3. Non-Goals

1. The app will not scrape at high frequency by default.
2. The app will not be a general-purpose browser automation platform.

## 4. Target Users

### 4.1 Primary User: Personal Availability Watcher

A user wants to know when something becomes available: a Steam Controller, GPU, concert ticket, product restock, limited merch drop, event registration slot, or appointment slot.

Needs:

- Fast setup.
- Minimal technical language.
- “I don’t know what in-stock looks like” support.
- Reliable push notification.
- Low false positives.
- Screenshot/history to verify what changed.

### 4.2 Advanced User: Power Monitor Builder

A technical user wants fine-grained control over selectors, intervals, text normalization, cookies, browser profiles, webhooks, and data retention.

Needs:

- CSS selector/XPath input.
- Regex rules.
- JSON export/import.
- Logs.
- Per-monitor browser profiles.
- Pushover priority configuration.
- Webhook/extensibility hooks.

## 5. Key User Stories

### 5.1 Product Out-of-Stock Monitor

As a user, I want to select the product status area and tell the app “this is currently out of stock,” so that I get notified when that area no longer matches the out-of-stock state.

Acceptance criteria:

- User enters a URL.
- App renders the page.
- User selects a region or element.
- App captures the current text and screenshot as a baseline.
- User chooses “Current state is unavailable/out of stock.”
- App alerts when that text disappears, changes materially, or a positive purchase phrase appears.

### 5.2 Whole Page Change Monitor

As a user, I want to monitor an entire page for changes, so that I can detect updates even if I do not know where they will appear.

Acceptance criteria:

- User can choose “whole page.”
- App captures normalized text and screenshot baselines.
- App ignores common noisy content if configured.
- App shows a diff when a change is detected.

### 5.3 Specific Element Monitor

As a user, I want to monitor a CSS selector or clicked element, so that alerts only fire for a specific product status, button, price, or form field.

Acceptance criteria:

- User can click an element in a rendered preview.
- App records a robust selector.
- App can fall back to visual region monitoring if the selector becomes invalid.
- App warns if the selector matches multiple elements.

### 5.4 Unknown In-Stock Text Detection

As a user, I may not know what the in-stock message will say. I only know it currently says “Out of Stock.” I want the app to notify me when that bad state disappears.

Acceptance criteria:

- App supports a rule: “alert when current bad text is absent.”
- App supports fuzzy matching so minor punctuation/case changes do not cause false positives.
- App supports alerting when a purchase button appears, using a configurable phrase list.
- App includes a cooldown so the user is not spammed.

### 5.5 Alert Confirmation and History

As a user, I want to see why I was alerted, so that I can decide whether the alert is real.

Acceptance criteria:

- Each alert links to the page.
- Each alert includes the monitor name, old state, new state, and detected phrases if available.
- App stores before/after screenshots.
- App stores before/after normalized text.
- App has a history view with diffs.

## 6. Recommended Technology Stack

### 6.1 Architecture Choice

Use a self-hosted web app with a browser-rendering worker.

Recommended stack:

- Frontend: React + TypeScript + Vite + Tailwind CSS.
- Backend API: FastAPI.
- Browser automation: Playwright with Chromium.
- Database: SQLite for single-user/local use; PostgreSQL optional later.
- Job scheduling: APScheduler or a small internal async scheduler for v1; Redis/RQ or Dramatiq optional later.
- Notification provider: Pushover first; webhook abstraction for future providers.
- Deployment: Docker Compose.
- Reverse proxy/auth: optional Caddy, Traefik, Authelia, or Tailscale-only access.

Rationale:

- React is better than a static server-rendered UI for element selection, preview overlays, visual region selection, screenshot diff display, and rule editing.
- FastAPI is a good fit for a Python backend, typed request models, async endpoints, and direct integration with Playwright.
- Playwright is needed because many retail pages render meaningful content through JavaScript.
- SQLite is enough for a personal monitoring app and keeps deployment simple.
- Docker Compose keeps the app portable for a homelab.

### 6.2 Alternate Stack Options

#### Option A: FastAPI + React + Playwright + SQLite

Best default.

Pros:

- Clean UX.
- Easy to self-host.
- Python backend fits scraping/browser automation well.
- Single container or two-container deployment is straightforward.
- Good enough for single-user and small-team use.

Cons:

- Frontend build complexity.
- Playwright browser dependencies increase image size.

#### Option B: FastAPI + HTMX + Playwright + SQLite

Best for minimal codebase.

Pros:

- Simpler than React.
- Less frontend build tooling.
- Easier to maintain for a solo developer.

Cons:

- Element selection and visual diff UX will be clunkier.
- Harder to build a polished region-selection workflow.

#### Option C: Tauri Desktop App + Backend Service

Best for local desktop users only.

Pros:

- Feels like a native app.
- Can use local browser/session more naturally.

Cons:

- Worse for always-on monitoring.
- More packaging complexity.
- Not ideal for homelab/server deployment.

Recommended: Option A.

## 7. Core Concepts

### 7.1 Monitor

A monitor is a saved configuration that checks one URL on a schedule.

Fields:

- Name.
- URL.
- Enabled/disabled.
- Check interval.
- Detection mode.
- Baseline snapshot.
- Alert rules.
- Notification settings.
- Browser profile/cookies setting.
- Cooldown and retry policy.

### 7.2 Snapshot

A snapshot is the captured state of a page or element at one point in time.

Fields:

- Timestamp.
- Final URL after redirects.
- HTTP status if available.
- Page title.
- Selected element text.
- Normalized text.
- HTML snippet.
- Screenshot path.
- Screenshot perceptual hash.
- Extracted status phrases.
- Price/button candidates if detected.

### 7.3 Check Run

A check run is one execution of a monitor.

Fields:

- Monitor ID.
- Start time.
- End time.
- Result status: unchanged, changed, alert_sent, failed, throttled, blocked, selector_missing.
- Error message.
- Change score.
- Triggered rule IDs.

### 7.4 Alert

An alert is a notification event sent to Pushover.

Fields:

- Monitor ID.
- Check run ID.
- Alert status: pending, sent, failed, suppressed.
- Pushover response.
- Retry count.
- Deduplication key.

## 8. Detection Modes

### 8.1 Whole Page Text Change

The app loads the page, extracts visible text, normalizes it, compares it against the previous baseline, and alerts if the difference exceeds a threshold.

Useful for:

- News/update pages.
- Generic change detection.
- Pages where the relevant area is unknown.

Default behavior:

- Ignore whitespace-only changes.
- Ignore timestamps if configured.
- Ignore script/style text.
- Alert only if text diff exceeds a configurable threshold.

### 8.2 Whole Page Visual Change

The app captures a screenshot and compares it with the previous screenshot.

Useful for:

- Pages where text extraction is unreliable.
- Heavily graphical product pages.
- Pages with dynamic content rendered as images/canvas.

Default behavior:

- Compare perceptual hash and pixel difference.
- Allow masking regions.
- Ignore minor anti-aliasing/layout shifts.

### 8.3 Specific Element Text Change

The app monitors one selected element by CSS selector, XPath, or generated selector.

Useful for:

- Product status labels.
- Price fields.
- Buttons.
- Appointment availability sections.

Default behavior:

- Alert when text changes materially.
- Alert if element disappears, if configured.
- Alert if selector becomes invalid after repeated failures.

### 8.4 Specific Element Visual Change

The app screenshots only the selected element or selected rectangular region.

Useful for:

- Status cards.
- Button areas.
- Dynamic widgets.
- Cases where text is unstable but visual state is clear.

Default behavior:

- Compare selected-region screenshot.
- Keep before/after crops.
- Prefer this mode when text extraction is unreliable.

### 8.5 Bad-State Disappearance

The user identifies the current state as bad, such as “Out of Stock,” “Unavailable,” “Sold Out,” or “No appointments.” The app alerts when that bad state disappears or materially changes.

Useful for:

- Product restocks.
- Appointment slot openings.
- Registration pages.
- “Coming soon” to “available” transitions.

Default behavior:

- Capture current selected text as bad-state baseline.
- Use normalized comparison.
- Use fuzzy matching to avoid false alerts from case/punctuation changes.
- Alert when bad phrases are gone or the selected area changes significantly.

Example rule:

- Current bad text: “Out of Stock.”
- Alert when selected text no longer contains “out of stock.”
- Also alert when selected area contains one of: “add to cart,” “buy now,” “reserve,” “available,” “pre-order.”

### 8.6 Positive Phrase Appearance

The app alerts when selected text or page text contains one of a configured set of positive phrases.

Default phrase groups:

- Retail: “add to cart,” “buy now,” “in stock,” “available,” “reserve,” “pre-order,” “checkout.”
- Tickets/events: “select seats,” “tickets available,” “register,” “book now.”
- Appointments: “available appointments,” “select time,” “open slot.”

### 8.7 Regex Rule

Advanced users can define regex rules.

Examples:

- Alert when price drops below a threshold.
- Alert when `Add to Cart` appears.
- Alert when a date field changes.

### 8.8 Numeric Rule

For prices, counts, or quantities, the app can extract a number and compare it.

Examples:

- Price below `$100`.
- Quantity greater than `0`.
- Slot count greater than `0`.

## 9. Monitor Creation UX

### 9.1 Guided Wizard

The main UX should be a guided flow:

1. Enter URL.
2. App loads rendered preview.
3. User chooses what to monitor:
   - Whole page.
   - Click an element.
   - Draw a region.
   - Advanced selector.
4. App shows detected text and screenshot.
5. User chooses what kind of alert they want:
   - Any meaningful change.
   - Current state disappears.
   - Text appears.
   - Price/number changes.
   - Advanced condition.
6. App suggests default rules.
7. User configures interval and Pushover priority.
8. User tests the monitor.
9. User saves.

### 9.2 “I Don’t Know the In-Stock Message” Flow

This should be a first-class path.

User-facing wording:

- “This page currently shows the unavailable state. Notify me when this changes.”

Internally, the app should:

- Capture selected text as the bad-state baseline.
- Extract likely bad phrases.
- Store screenshot and normalized text.
- Create a composite rule:
  - Alert when bad phrase disappears.
  - Alert when positive phrase appears.
  - Alert when visual region changes above threshold.

### 9.3 Preview and Selector Picking

The preview should show the actual rendered page in an embedded controlled browser or screenshot-based preview.

Element selection requirements:

- User can hover elements and see a highlight.
- User can click an element to select it.
- App shows selected text.
- App shows generated selector.
- App warns if selector is too broad or fragile.
- App allows “monitor parent element” if the selected element is too narrow.
- App allows “draw region” when element selection is not reliable.

### 9.4 Baseline Capture

Before saving, the app should show:

- Current text.
- Current screenshot.
- Detected bad phrases.
- Detected positive phrases if any.
- Final URL.
- Timestamp.
- Whether JavaScript rendering was used.

The user must be able to refresh the baseline before saving.

## 10. Alerting Requirements

### 10.1 Pushover Integration

Required Pushover settings:

- User key.
- App token.
- Default device, optional.
- Default priority.
- Emergency retry/expire settings, optional.
- Quiet hours, optional.

Alert content:

- Title: monitor name.
- Message: concise change summary.
- URL: monitored page.
- Optional URL title: “Open page.”
- Priority: configurable per monitor.

Example alert:

```text
Steam Controller Restock
Status area changed from “Out of Stock” to “Add to Cart”.
```

For unknown target state:

```text
Steam Controller Restock
Unavailable text disappeared from the monitored area. Check the page now.
```

### 10.2 Deduplication

The app must not spam the user.

Deduplication rules:

- Do not send repeated alerts for the same resulting state within cooldown window.
- Default cooldown: 30 minutes.
- Emergency mode can bypass cooldown once per state change.
- If state flips back to bad and then good again, alert again.

### 10.3 Alert Confirmation

After an alert, the app should mark the monitor as one of:

- Continue monitoring normally.
- Pause after alert.
- Require manual acknowledgement.
- Re-baseline after alert.

Default for restock monitors:

- Continue monitoring, but suppress duplicate alerts for the same state.

### 10.4 Test Alert

Each Pushover profile and each monitor must support a “Send test alert” button.

## 11. Scheduling Requirements

### 11.1 Check Intervals

Defaults:

- Standard monitor: every 15 minutes.
- Availability monitor: every 3 minutes.
- High-priority monitor: every 1 minute.

Minimum recommended interval:

- 60 seconds for self-hosted personal use.

The app should warn users when choosing aggressive intervals.

### 11.2 Jitter

The app should add random jitter to check times to avoid hammering a site on exact intervals.

Example:

- Configured interval: 3 minutes.
- Actual check: 3 minutes ± 20 seconds.

### 11.3 Failure Backoff

If a site repeatedly fails, the app should back off.

Examples:

- First failure: retry next interval.
- 3 failures: double interval temporarily.
- 5 failures: mark as degraded and notify optionally.

### 11.4 Concurrency

Default concurrency should be low.

- v1 default: 2 concurrent browser checks.
- Per-domain limit: 1 concurrent check.
- Global browser context pool to reduce overhead.

## 12. Browser and Session Requirements

### 12.1 Rendering

The app must support:

- JavaScript-rendered pages.
- Waiting for network idle or selected element presence.
- Custom wait time after page load.
- Screenshots.
- Element screenshots.
- Mobile/desktop viewport options.

### 12.2 Cookies and Login Sessions

The app should support monitors that need login state.

v1 approach:

- Per-monitor or per-domain browser storage state.
- User can open an interactive browser session to log in.
- App saves cookies/storage state.

Security requirements:

- Store browser state under app data directory.
- Do not display cookies in UI.
- Allow deleting stored session data.
- Warn users not to store sensitive login sessions unless necessary.

### 12.3 Headers and Locale

The app should allow:

- User-agent selection.
- Accept-language setting.
- Timezone setting.
- Viewport size.

Defaults:

- Desktop Chromium viewport.
- User’s local timezone, configurable.

## 13. Noise Reduction

### 13.1 Text Normalization

Before comparison, normalize:

- Whitespace.
- Case, optionally.
- Unicode normalization.
- Repeated punctuation.
- Dynamic timestamps, if detected.
- Tracking query parameters, if comparing URLs.

### 13.2 Ignore Rules

Users should be able to ignore:

- Specific text patterns.
- CSS selectors.
- Visual regions.
- Date/time strings.
- Ad/recommendation/sidebar areas.

### 13.3 Change Thresholds

Each monitor should have thresholds:

- Text similarity threshold.
- Visual difference threshold.
- Minimum changed characters.
- Minimum changed area percentage.

Default for selected product area:

- Low threshold: alert on most meaningful changes.

Default for whole page:

- Higher threshold: avoid false positives.

## 14. Diff and History UX

The app should include a history page per monitor.

History view:

- Timeline of checks.
- Status: unchanged, changed, alert sent, failed.
- Before/after text diff.
- Before/after screenshots.
- Highlighted visual differences.
- Pushover delivery status.
- Manual “make this the new baseline” button.

The history should help answer:

- What changed?
- Was this a false positive?
- Did an alert send successfully?
- Should the baseline be updated?

## 15. Data Model Draft

### 15.1 Monitor

```text
id
name
url
enabled
mode
selector
region_json
baseline_snapshot_id
interval_seconds
jitter_seconds
cooldown_seconds
pushover_profile_id
priority
pause_after_alert
created_at
updated_at
last_checked_at
last_alerted_at
```

### 15.2 Snapshot

```text
id
monitor_id
created_at
final_url
page_title
http_status
raw_text_path
normalized_text_path
html_snippet_path
screenshot_path
element_screenshot_path
text_hash
visual_hash
metadata_json
```

### 15.3 Rule

```text
id
monitor_id
type
config_json
enabled
created_at
updated_at
```

Rule types:

- any_text_change.
- any_visual_change.
- bad_text_absent.
- positive_phrase_present.
- regex_match.
- numeric_threshold.
- selector_missing.

### 15.4 CheckRun

```text
id
monitor_id
started_at
finished_at
status
change_score
triggered_rules_json
error_message
snapshot_id
alert_id
```

### 15.5 PushoverProfile

```text
id
name
user_key_encrypted
app_token_encrypted
default_device
default_priority
created_at
updated_at
```

## 16. API Requirements

### 16.1 Monitor APIs

- `GET /api/monitors`
- `POST /api/monitors`
- `GET /api/monitors/{id}`
- `PATCH /api/monitors/{id}`
- `DELETE /api/monitors/{id}`
- `POST /api/monitors/{id}/check-now`
- `POST /api/monitors/{id}/pause`
- `POST /api/monitors/{id}/resume`
- `POST /api/monitors/{id}/rebaseline`

### 16.2 Preview APIs

- `POST /api/preview/load`
- `POST /api/preview/select-element`
- `POST /api/preview/capture-region`
- `POST /api/preview/test-rule`

### 16.3 Alert APIs

- `GET /api/pushover-profiles`
- `POST /api/pushover-profiles`
- `POST /api/pushover-profiles/{id}/test`
- `GET /api/alerts`

### 16.4 History APIs

- `GET /api/monitors/{id}/runs`
- `GET /api/monitors/{id}/snapshots/{snapshot_id}`
- `GET /api/monitors/{id}/diff?from=...&to=...`

## 17. Frontend Requirements

### 17.1 Main Screens

1. Dashboard.
2. New monitor wizard.
3. Monitor detail page.
4. History/diff page.
5. Settings page.
6. Pushover profile page.

### 17.2 Dashboard

Show:

- Monitor name.
- URL domain.
- Current status.
- Last check time.
- Last change time.
- Last alert time.
- Enabled/paused.
- Quick actions: check now, pause, edit, open page.

### 17.3 New Monitor Wizard

Must prioritize fast setup.

The best default flow:

1. URL.
2. Render preview.
3. Click product status area.
4. Choose “currently unavailable/out of stock.”
5. Test rule.
6. Save.

Advanced options should be collapsed by default.

### 17.4 Monitor Detail

Show:

- Current baseline.
- Latest observed state.
- Rules.
- Interval.
- Alert settings.
- Recent checks.
- Manual actions.

### 17.5 History/Diff

Show:

- Before/after screenshots.
- Text diff.
- Triggered rule.
- Notification result.
- Button to mark alert as false positive.
- Button to update baseline.

## 18. Backend Service Requirements

### 18.1 Scheduler

The scheduler should:

- Load enabled monitors.
- Compute next check time with jitter.
- Respect per-domain limits.
- Queue checks.
- Record check results.
- Trigger alerts.

### 18.2 Browser Worker

The browser worker should:

- Launch Chromium via Playwright.
- Use persistent browser contexts when configured.
- Navigate to URL.
- Wait for page load or selected selector.
- Extract text.
- Capture screenshots.
- Return structured snapshot data.

### 18.3 Comparator

The comparator should:

- Load baseline snapshot.
- Compare new snapshot.
- Evaluate rules.
- Produce change summary.
- Decide whether alert is needed.
- Apply deduplication/cooldown.

### 18.4 Notifier

The notifier should:

- Send Pushover messages.
- Retry transient failures.
- Record delivery status.
- Suppress duplicate alerts.
- Support test notifications.

## 19. Security Requirements

1. Store Pushover tokens encrypted at rest if practical.
2. Never log Pushover tokens.
3. Never expose cookie/session data in UI.
4. Support deleting browser profile data.
5. Default to LAN/Tailscale-only deployment.
6. Provide optional app password or reverse-proxy auth guidance.
7. Avoid storing full page HTML indefinitely unless the user enables it.
8. Redact common secrets from captured text where possible.

## 20. Privacy Requirements

1. All monitoring data should stay local by default.
2. No analytics or telemetry by default.
3. Screenshots may contain private content; users must be able to delete them.
4. Retention settings should be configurable.

Default retention:

- Check runs: 90 days.
- Screenshots: 30 days.
- Alert records: 180 days.
- Failed run logs: 30 days.

## 21. Ethical and Site-Compatibility Requirements

1. Use reasonable default intervals.
2. Do not bypass CAPTCHAs.
3. Do not rotate proxies to evade blocking.
4. Do not automate checkout or purchasing.
5. Respect robots/site terms where applicable.
6. Provide per-domain rate limits.
7. Identify the app with a reasonable user agent if configured by user.

## 22. Configuration Requirements

Environment variables:

```text
APP_BASE_URL
DATA_DIR
DATABASE_URL
SECRET_KEY
DEFAULT_CHECK_INTERVAL_SECONDS
MAX_CONCURRENT_CHECKS
PLAYWRIGHT_BROWSERS_PATH
LOG_LEVEL
```

Optional:

```text
PUSHOVER_DEFAULT_USER_KEY
PUSHOVER_DEFAULT_APP_TOKEN
AUTH_USERNAME
AUTH_PASSWORD_HASH
TZ
```

## 23. Docker Deployment Requirements

The app should support Docker Compose.

Recommended services:

- `watcher-app`: FastAPI backend + frontend static files.
- `watcher-worker`: optional separate worker for browser checks.
- `watcher-db`: optional PostgreSQL for future multi-user deployments; not needed for SQLite mode.

v1 can run as one container:

- FastAPI API.
- Static frontend.
- Scheduler.
- Playwright Chromium.
- SQLite data volume.

Mounts:

- `/data/db`.
- `/data/screenshots`.
- `/data/browser-profiles`.
- `/data/logs`.

## 24. MVP Scope

### 24.1 MVP Features

1. Create/edit/delete monitors.
2. Render page with Playwright.
3. Select element by clicking in preview.
4. Monitor selected element text.
5. Monitor selected element screenshot.
6. Monitor whole page text.
7. “Current state is bad; alert when it changes” rule.
8. Positive phrase appearance rule.
9. Pushover integration.
10. Check now.
11. Screenshot and text history.
12. Deduplication and cooldown.
13. Docker deployment.

### 24.2 MVP Exclusions

1. Multi-user accounts.
2. Mobile app.
3. Browser extension.
4. CAPTCHA handling.
5. Proxy rotation.
6. Auto checkout.
7. Complex workflow automation.
8. Full visual diff heatmaps.
9. PostgreSQL requirement.
10. Public SaaS deployment.

## 25. V1.1 Features

1. Draw-to-select visual regions.
2. Regex rules.
3. Numeric threshold rules.
4. Ignore selectors.
5. Ignore visual regions.
6. Import/export monitor configs.
7. Multiple Pushover profiles.
8. Manual login/session capture flow.
9. Webhook notification provider.
10. Per-domain settings.

## 26. V2 Features

1. Browser extension for one-click monitor creation.
2. Multi-user support.
3. Teams/shared monitors.
4. Mobile-friendly PWA.
5. Advanced visual diff overlays.
6. Machine-assisted stock status classification.
7. Template library for common sites.
8. Optional PostgreSQL deployment.
9. Distributed workers.
10. Prometheus/Grafana metrics.

## 27. Suggested Development Milestones

### Milestone 1: Backend Skeleton

- FastAPI project.
- SQLite models.
- Monitor CRUD.
- Pushover test endpoint.
- Basic scheduler loop.

### Milestone 2: Browser Capture

- Playwright page load.
- Whole-page text extraction.
- Whole-page screenshot.
- Snapshot storage.
- Manual check endpoint.

### Milestone 3: Element Monitoring

- Selector-based extraction.
- Element screenshot.
- Baseline capture.
- Text comparison.
- Alert on change.

### Milestone 4: Guided UI

- React dashboard.
- New monitor wizard.
- Rendered screenshot preview.
- Element selection.
- Save monitor flow.

### Milestone 5: Restock Intelligence

- Bad-state disappearance rule.
- Positive phrase rule.
- Deduplication.
- Cooldown.
- Alert history.

### Milestone 6: Hardening

- Failure backoff.
- Per-domain limits.
- Retention cleanup.
- Docker image.
- Basic auth.
- Logs and diagnostics.

## 28. Important UX Details

### 28.1 Default Restock Rule

When the user selects a product area and chooses “currently unavailable,” create this composite rule:

1. Alert if current bad phrase disappears.
2. Alert if positive purchase phrase appears.
3. Alert if selected region visually changes significantly.
4. Suppress duplicates for 30 minutes.
5. Keep monitoring after alert.

This solves the central problem: the user does not need to know what the in-stock message looks like.

### 28.2 Recommended User Copy

Use wording like:

- “Notify me when this unavailable state changes.”
- “The app will watch the selected area and alert when the current text disappears or the area changes significantly.”
- “You do not need to know the future in-stock message.”
- “False positives can happen when a page layout changes. The alert will include before/after screenshots.”

Avoid wording like:

- “Scrape.”
- “Bypass.”
- “Bot.”
- “Guaranteed restock detection.”

### 28.3 Alert Quality

A good alert should answer three questions:

1. What changed?
2. Why did I get notified?
3. What should I click now?

Example:

```text
Steam Controller
Unavailable text disappeared from the monitored purchase box.
Old: Out of Stock
New: $99.00 Add to Cart
```

## 29. Risks and Mitigations

### 29.1 Dynamic Page Noise

Risk: Page changes frequently due to recommendations, banners, tracking, or localization.

Mitigation:

- Encourage selected element/region monitoring.
- Provide ignore regions/selectors.
- Use thresholds.

### 29.2 Selector Breakage

Risk: CSS selector changes after deployment.

Mitigation:

- Store multiple selector candidates.
- Support visual region fallback.
- Alert on repeated selector missing.

### 29.3 False Positives

Risk: The app alerts when the product is still unavailable.

Mitigation:

- Composite rules.
- Screenshot diffs.
- Cooldowns.
- False-positive feedback button.

### 29.4 Missed Restocks

Risk: Product comes in stock between checks and sells out before next check.

Mitigation:

- Allow 1-minute interval for critical monitors.
- Use Pushover high-priority alerts.
- Keep checks lightweight.
- Warn that no polling app can guarantee detection.

### 29.5 Site Blocking

Risk: Frequent browser checks trigger rate limits or blocks.

Mitigation:

- Conservative defaults.
- Per-domain limits.
- Backoff on errors.
- Do not use evasion techniques.

## 30. Success Metrics

MVP is successful if:

1. A user can create a Steam Controller-style restock monitor in under 2 minutes.
2. The app can detect a selected element changing from “Out of Stock” to another state.
3. The app can send a Pushover alert with a useful summary and URL.
4. The app stores enough history to explain every alert.
5. The app runs reliably for at least 30 days on a home server without manual intervention.

## 31. Recommended MVP Implementation Decision

Build the MVP as:

- Python backend with FastAPI.
- Playwright Chromium for page rendering.
- SQLite database in WAL mode.
- React + TypeScript + Tailwind frontend.
- Pushover notification provider.
- Docker Compose deployment.

This provides the cleanest balance of user experience, reliability on JavaScript-heavy pages, and simple self-hosting. The most important product decision is to make “current state is bad; alert when it changes” a first-class monitoring mode rather than forcing the user to know the future desired text.

