# AI Agent Instructions for this Repo

Purpose: Help AI coding agents be productive quickly in this Flask + SQLAlchemy + NFC (ACR122U/pyscard) app. Prefer concrete edits over advice and follow the patterns below.

## Architecture (what lives where)
- Web app entry: `app.py` (Flask). Uses `frontend/templates` and `frontend/static`. CORS + Flask-Login + SQLAlchemy. DB is `sqlite:///database/cafeteria.db` by default.
- Data layer: `backend/models.py`. Key enums: `UserRole`, `TransactionType`, `CardStatus`. Key models: `Student`, `Card`, `MenuItem`, `Transaction`, `TransactionItem`, `Operator`, `SystemLog`, `OfflineTransaction`. `init_db(app)` auto-creates tables and a default admin.
- NFC integration: `backend/nfc_service.py` exposes `get_nfc_service(key)` returning a singleton `NFCCardService`. Reads/writes balance and student_id to card, with an offline SQLite cache at `database/offline_cards.db` and a pending transaction queue for sync.
- Standalone reader utility: `nfc_reader_service.py` and `test_reader.py` (pyscard, useful for hardware checks). Not used by the Flask app directly.
- Frontend: Jinja templates in `frontend/templates` (e.g., `login.html`, `dashboard.html`, `pos.html`) and JS/CSS under `frontend/static`.

## Core flows and patterns
- Auth: `Operator` users via Flask-Login. Use `login_required` on routes. Admin check via `current_user.is_admin`.
- NFC read/write: The Flask routes in `app.py` call `nfc_service = get_nfc_service(os.getenv('NFC_ENCRYPTION_KEY'))` then use:
  - `nfc_service.connect_reader()` → ensure hardware availability
  - `nfc_service.wait_for_card(timeout=10)` → get `card_uid`
  - `nfc_service.read_card(card_uid)` / `write_card(card_uid, balance, student_id)`
  - Offline fallback: reads may return `from_cache: True`; writes always update cache.
- Transactions: When changing balances, always create a `Transaction` record and log via `SystemLog`. Ex: see `/api/card/load`, `/api/transaction/purchase`, `/api/transaction/refund` in `app.py`.
- Money: Use `decimal.Decimal` and store in Numeric columns; convert to `float()` only in JSON responses.
- Enums stored as strings: Use `.value` (e.g., `TransactionType.PURCHASE.value`). Card status gate checks are required before mutations.

## Local run & workflows
- Env: copy `.env.example` → `.env`; important vars: `SECRET_KEY`, `DATABASE_URL`, `NFC_ENCRYPTION_KEY` (auto-generated if missing).
- Setup DB and sample data: `python setup.py` (creates admin `admin/admin123` and operator `operator/operator123`).
- Run dev server: `python app.py` → http://localhost:5000. Creates `database/` if missing.
- NFC checks: `python test_reader.py` (quick) or `python nfc_reader_service.py` (continuous monitor). On macOS you may need to restart pcscd.

## Route conventions (examples in `app.py`)
- Web pages: `/login`, `/` (dashboard), `/pos`, `/menu`, `/students`, `/reports` → render templates under `frontend/templates`.
- API endpoints: `/api/...` return JSON and centralize error format: `{ success: bool, error?: str }`. 404/500 handlers return JSON for `/api/*` paths.
- Typical pattern when mutating card state:
  1) Load entities (e.g., `Card` by `card_uid`) and validate status/inputs
  2) Update balance via `card.add_funds()` or `card.deduct_funds()`
  3) Persist and mirror to card with `nfc_service.write_card(card_uid, card.balance, student_id)`
  4) Create `Transaction` (+ optional `TransactionItem`s)
  5) Append `SystemLog` and commit (rollback on exceptions)

## Project-specific gotchas
- Hardware optional: When no reader is connected, `nfc_service.read_card` may fall back to offline cache; plan for `from_cache` and missing `student_id`.
- Mifare default keys (0xFF…): Change for production. Balance encryption in `nfc_service` is simple XOR; Fernet is used for service-level payloads only.
- Decimal handling: Always wrap inputs via `Decimal(str(value))` (see patterns in `app.py`).
- Authorization: Guard admin-only operations (e.g., create/update menu items, refunds) with `current_user.is_admin`.
- Singleton NFC service: Do not instantiate `NFCCardService` directly—use `get_nfc_service()` to share connection/cache.

## Extending the system
- New API route: Place in `app.py` (or a blueprint if you add one). Follow error/JSON patterns and transaction/log creation.
- New data fields: Add to `backend/models.py`, run `python setup.py` or start app to let SQLAlchemy create columns (SQLite); consider migrations if you add Alembic later.
- Frontend changes: Update `frontend/templates/*.html` and wire JS in `frontend/static/js/app.js`. Keep server-rendered data minimal; fetch via `/api/...` as needed.

## References in repo
- `app.py`: All route patterns and end-to-end flows
- `backend/models.py`: Data model, enums, auth helpers
- `backend/nfc_service.py`: Reader I/O, offline cache, sync helpers
- `setup.py`: Sample data & default users
- `WARP.md`: Full setup/run commands and architecture summary

If anything here feels off or missing (e.g., additional blueprints, CLI tasks, or build steps), ask the user to confirm and we’ll update this file.