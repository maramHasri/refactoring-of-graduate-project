# edu_forms — Multi-Tenant Assessment Platform (Flask)

PostgreSQL-backed Flask API for **edu_forms**. Models and schemas are being rebuilt table-by-table from the ERD.

## Stack

- Flask 3 + Flask-SQLAlchemy
- PostgreSQL
- Alembic (Flask-Migrate)
- Marshmallow schemas
- Layered architecture: `router/` → `service/` → `repositories/` → `models/`

## Project layout

```
config/          # Settings
models/          # SQLAlchemy models (pending — per-table)
router/          # HTTP blueprints (health only until models exist)
service/         # Business logic (pending)
repositories/    # Data access (pending)
schemas/         # Marshmallow validation (pending)
seeds/           # Enum + plan seed data
migrations/      # Alembic revisions
utils/           # db, enums, security
scripts/         # DB bootstrap
run.py           # Entry point
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Create database:

```bash
python scripts/create_database.py
```

Initialize migrations and apply:

```bash
set FLASK_APP=run.py
flask db init
flask db migrate -m "Initial ERD schema"
flask db upgrade
flask seed
```

Run API:

```bash
python run.py
```

Health: `GET http://localhost:5000/health`  
Enums: `GET http://localhost:5000/api/enums`

## Next step

Provide each ERD table definition; models and matching schemas will be added one at a time.

## Environment

Copy `.env.example` to `.env` and set `DATABASE_URL`, `SECRET_KEY`, and integration keys.
