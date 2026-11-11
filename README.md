# DhioGame

Real-time multiplayer drawing game: players join private rooms, draw from reference images, and reveal results together. See [`PRD.md`](./PRD.md) for the product requirements.

This repository currently contains the backend foundation (FastAPI, SQLAlchemy 2.0, Alembic, Neon PostgreSQL). Gameplay, WebSockets, and the frontend are not implemented yet.

## Project Structure

```
backend/
  alembic/              Alembic environment and migrations
  app/
    api/routes/         HTTP route modules (health check)
    core/               Application settings
    db/                 SQLAlchemy base, engine, and session
    models/             ORM models and enums
    schemas/            Pydantic schemas (reserved for later tasks)
    services/           Business logic (reserved for later tasks)
    main.py             FastAPI application factory
  alembic.ini
  requirements.txt
frontend/               Frontend placeholder
tests/                  Test package placeholder
.env.example            Environment variable template
```

## Prerequisites

- Python 3.11+ (3.12 recommended)
- A [Neon](https://neon.tech) PostgreSQL database

## Setup

1. Create and activate a virtual environment:

   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

3. Create your local environment file from the template (skip this if `.env` already exists):

   ```powershell
   Copy-Item ..\.env.example ..\.env
   ```

4. Edit `.env` and set `DATABASE_URL` to your Neon connection string. Copy it from the Neon dashboard (the pooled connection string is recommended). Both `postgresql://` and `postgresql+psycopg://` URLs are supported.

## Database Migrations

Run Alembic from the `backend` directory. It loads `DATABASE_URL` from the repository root `.env`.

```powershell
# Apply all migrations (creates the tables)
alembic upgrade head

# Create a new migration after changing models
alembic revision --autogenerate -m "describe the change"
alembic upgrade head

# Roll back the most recent migration
alembic downgrade -1
```

The initial migration creates `rooms`, `players`, `games`, `reference_images`, `assignments`, `drawings`, and `reveals`.

## Run the API

From the `backend` directory:

```powershell
uvicorn app.main:app --reload
```

- API root: <http://127.0.0.1:8000/>
- Health check: <http://127.0.0.1:8000/api/health>
- Interactive docs: <http://127.0.0.1:8000/docs>

Verify the health check with:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

A healthy response is:

```json
{"status": "ok", "database": "ok"}
```

If the database cannot be reached, the endpoint returns HTTP `503` with `{"status": "unhealthy", "database": "unreachable"}`.

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes | — | Neon PostgreSQL connection string. Never commit real credentials. |
| `APP_NAME` | No | `DhioGame API` | Application title shown in the docs. |
| `ENVIRONMENT` | No | `development` | Deployment environment label. |
| `DEBUG` | No | `false` | Enables FastAPI debug mode. |
| `CORS_ORIGINS` | No | `http://localhost:5500,http://127.0.0.1:5500` | Comma-separated allowed frontend origins. |

`.env` is git-ignored. Only `.env.example` is committed.

## Data Model

- **Room** — join code, host, status, settings, expiry.
- **Player** — room membership, nickname, role, connection status, hashed reconnection token.
- **Game** — room, mode, current phase, durations, timestamps.
- **ReferenceImage** — game, storage key, and upload metadata.
- **Assignment** — one reference image per player per game (unique, no duplicates).
- **Drawing** — player/game canvas data and submission status.
- **Reveal** — randomized reveal order and current index for a game.

## Manual Follow-up

- Set a real Neon `DATABASE_URL` in `.env` before running migrations.
- Configure the production environment variable `DATABASE_URL` on the backend host (do not upload `.env`).
- Temporary object storage for reference images and drawings is not implemented yet.
