# Inventra remediation

This note records the defects fixed in the audit-remediation branch, the
decisions taken, and what still needs a human decision or a manual step.

## How to run and verify

Backend (from `backend/`):

    python -m venv .venv
    .venv\Scripts\pip install -r requirements-dev.txt
    alembic upgrade head
    uvicorn app.main:app --port 8000
    python -m pytest            # uses a database whose name contains "test"

Frontend (from `frontend/`):

    npm ci
    npm run lint
    npx tsc --noEmit
    npm run build
    npm start                   # http://localhost:3000

Demo data: `python -m app.database.seed_consumption` adds 120 days of
synthetic consumption. It does not change on-hand quantities.

## Backend changes

- **Migrations.** The inventory, consumption, purchase-order and override tables
  had no migration. Baseline `b983ce5438b1` creates them and is idempotent.
  `c4f1a7e9d2b3` adds assistant conversation context columns and the database
  rule that reserved stock may not exceed on-hand stock. The second step stops
  with a clear message if existing data would violate it.
- **Forecasting.** Periods lie on a fixed 30-day grid anchored at 2026-01-01, so
  manual overrides stay attached to their period. Zero demand and new items
  return a status (`ok`, `no_demand`, `insufficient_data`) instead of an error.
  Untracked history is not averaged in as zero: if consumption tracking starts
  inside the 90-day window, the forecast reports `insufficient_data` and says
  when a full window will be available.
- **Stock risk.** Average daily demand is measured over the days actually
  tracked. A single policy module defines reorder point, risk level and
  suggested order, and is used by stock risk, analytics and the assistant.
  Draft and pending purchase orders are not counted as incoming stock.
- **Integrity.** Consumption locks the item row and rejects future dates.
  Inventory updates lock the row and cannot clear required fields. PO creation
  checks the item is active and handles duplicate numbers cleanly.
- **Errors.** Database outages return 503. Unexpected errors return a generic
  500 with no stack trace or SQL.
- **Assistant.** Rebuilt as a deterministic understanding layer, answer builders
  that read only from PostgreSQL, and a thin router. It supports greetings and
  small talk, follow-ups through the conversation's current item, ambiguity
  questions, multi-intent messages, what-if scenarios (never saved), refusal of
  write requests, and honest refusal of unsupported analyses.
- **Language model (Groq).** Off by default (`ASSISTANT_LLM_ENABLED=false`).
  When enabled it receives only the user's latest message and may return only
  fixed intent labels. Any failure falls back to the rule-based path.
- **Conversation memory.** The summary is updated incrementally with a watermark,
  so older questions are no longer dropped after 30 messages.
- **Removed.** The duplicate `app/api/main.py`, the broken `test_mistral.py`,
  and the empty `forecast_calculations.py` and `procurement/` placeholders.

## Frontend changes

- One responsive `AppShell` (sidebar on wide screens, drawer on small screens)
  replaces four copies of the navigation. Dead Activity and Settings links are
  removed. A real Help & Support page is added.
- Dashboard: "needs attention" uses the backend's risk levels, including
  low stock. The unit-mixing "available stock" total is replaced by counts. The
  status badge reflects whether data loaded.
- Forecasting: units follow each item, and new or zero-demand items show their
  status message rather than a misleading zero.
- Purchase orders: the initial load is cancellation-safe; Refresh is separate.
- Assistant: message IDs are assigned in handlers; a failed send is restored to
  the input rather than shown as sent; intents are shown in plain language; the
  service status comes from the real health endpoint; the delete control is
  visible on touch screens; Enter does not send during IME composition.
- API client: shows the backend's own error messages, times out stalled
  requests, and pages through the full inventory list.
- Fonts are self-hosted through the `geist` package, so the build no longer
  depends on Google Fonts.
- Placeholder-name filters (records named "string") are removed. The records
  are shown as they are.

## Decisions to confirm

1. Reorder point is the calculated value, floored at the configured reorder level.
2. Suggested order restores the reorder point; it does not fill to a maximum level.
3. Overrides are keyed to the fixed 30-day period that contains their start date.
4. The language model is off by default. Enabling it requires approval for
   sending users' latest messages to an external API.
5. Untracked history is treated as unknown, not zero.

## Still open

- No authentication or roles. Any client that can reach the API can change data.
  This must be addressed before any shared deployment.
- Existing databases may contain test rows (for example, items named "string"
  from API testing). They now appear in the interface and should be deactivated
  through the API or the database.
- Visual layout on phones and the drawer were not checked in a real browser in
  this environment. Please check them locally with `npm start`.
- Forecasts use a three-period moving average. More advanced methods should wait
  for more history.
