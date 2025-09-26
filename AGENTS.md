# Repository Guidelines

## Project Structure & Module Organization
- `app.py` orchestrates the Flask web app, wiring templates, API routes, and the NFC service; keep new views thin and delegate to helpers under `backend/`.
- Core models live in `backend/models.py`; extend or migrate database logic here and store supporting services (for example `backend/nfc_service.py`).
- UI assets sit in `frontend/templates/` and `frontend/static/`; SQLite data files land in `database/`, and hardware helpers such as `nfc_reader_service.py` stay at the repo root.

## Build, Test, and Development Commands
- `./scripts/devshell.sh` creates/activates the virtualenv and runs commands; start local servers with `./scripts/devshell.sh python app.py`.
- `python setup.py` initializes the schema and loads demo operators, menu items, and students.
- Run automated checks with `./scripts/devshell.sh pytest`; verify NFC hardware separately via `python test_reader.py` before POS testing.

## Coding Style & Naming Conventions
- Follow PEP 8: 4-space indentation, double quotes for strings, and module-level docstrings mirroring existing files.
- Use `snake_case` for functions, Flask routes, and helper modules, `PascalCase` for SQLAlchemy models, and descriptive template names like `dashboard.html`.
- Keep business rules in reusable methods (`Card.add_funds`, `Operator.set_password`) and document non-obvious flows with concise comments or docstrings.

## Testing Guidelines
- Primary target framework is `pytest`; place new tests under `tests/` using `test_*.py` naming and mirror package layout (e.g., `tests/backend/test_models.py`).
- Mock NFC hardware interactions where possible; reserve `python test_reader.py` for manual verification with an attached ACR122U reader.
- Aim to cover database transactions and error branches, especially when touching `backend/models.py` or API endpoints in `app.py`.

## Commit & Pull Request Guidelines
- Use conventional-style commits (`docs: add WARP.md ...`, `feat:`, `fix:`) and keep messages imperative and scoped.
- Before opening a PR, ensure the app boots via `python app.py`, seeded data loads with `python setup.py`, and automated tests pass locally.
- PR descriptions should summarize intent, note hardware impacts, link issues, and include UI screenshots for changes in `frontend/templates/`.

## Security & Configuration Tips
- Copy `.env.example` to `.env`, set `SECRET_KEY`, database URLs, and `NFC_ENCRYPTION_KEY`; never commit populated secrets or local `.db` files.
- Rotate default credentials created by `setup.py` in staging/production and update operators through the admin UI or migrations.
- When handling card data, reuse the encryption helpers in `backend/nfc_service.py` rather than introducing custom cryptography.
