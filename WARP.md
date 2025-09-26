# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Common Development Tasks

### Environment Setup

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your configuration
```

### Database Initialization

```bash
# Initialize database and create sample data
python setup.py
```

### Running the Application

```bash
# Start the Flask web application
./scripts/devshell.sh python app.py
# The app runs on http://localhost:5055 by default
```
Set a custom port by exporting `PORT`, e.g., `PORT=8081 ./scripts/devshell.sh python app.py`.

The helper script `scripts/devshell.sh` auto-activates the virtual environment (creating it if missing), installs dependencies when `requirements.txt` changes, and then runs the command you pass in. Run it with no arguments to spawn an interactive shell inside the venv.

### NFC Reader Operations

```bash
# Test NFC reader connectivity (ACR122U)
python test_reader.py

# Run NFC reader monitoring service (standalone)
python nfc_reader_service.py
```

### Testing

```bash
# Run a single test file (when tests are implemented)
pytest tests/test_models.py

# Run all tests
pytest
```

## Architecture Overview

This is a Flask-based school cafeteria payment system with NFC card support. Key components:

**Web Layer**
- Flask application (`app.py`) serving REST APIs and web interface
- Templates in `frontend/templates/` (login, dashboard, POS interface)
- Static assets in `frontend/static/`
- Session-based authentication with Flask-Login

**Data Layer**
- SQLAlchemy ORM with models in `backend/models.py`
- Main entities: Student, Card, MenuItem, Transaction, TransactionItem, Operator
- Two SQLite databases:
  - `database/cafeteria.db` - Main application database
  - `database/offline_cards.db` - Offline card data cache for resilience
  - `nfc_readings.db` - Standalone NFC reader service database

**NFC Integration**
- Uses ACR122U reader via pyscard library
- Service layer in `backend/nfc_service.py` handles:
  - Card encryption/decryption using Fernet
  - Offline caching for network-independent operation
  - Pending transaction queue for sync when online
- Standalone monitoring service (`nfc_reader_service.py`) for continuous card detection

**Security Features**
- Encrypted card data storage
- PIN support for cards (optional)
- Role-based access (Admin, Operator, Viewer)
- Password hashing with Werkzeug

## Important Context

### Hardware Requirements
- ACR122U NFC card reader (USB)
- Mifare Classic or compatible NFC cards

### Default Credentials
After running `setup.py`:
- **Admin**: username `admin`, password `admin123`
- **Operator**: username `operator`, password `operator123`

### Key Configuration
- Default port: 5055
- Database path: `sqlite:///database/cafeteria.db`
- NFC encryption key must be set in `.env` (auto-generated if not provided)

### Card Data Storage
- Balance stored in block 4
- Student ID in block 5
- Checksum in block 6
- Uses default Mifare keys (0xFF x6) - change in production

### Transaction Types
- LOAD_FUNDS - Add money to card
- PURCHASE - Buy items
- REFUND - Return transaction
- ADJUSTMENT - Manual balance correction
