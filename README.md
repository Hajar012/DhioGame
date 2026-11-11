# DhioGame

DhioGame is a private, real-time multiplayer drawing game. Players create a room, receive reference images, draw against the clock, and reveal the chaos together. See [`PRD.md`](./PRD.md) for the product requirements.

Current implementation includes:

- Private rooms with join codes, sessions, readiness, and live lobby sync.
- Host-controlled settings, image uploads, and game start.
- Same-image and random-assignment modes with private assignments.
- Server-authoritative viewing/drawing timers.
- Responsive canvas with brush, color, size, eraser, undo, redo, clear, submit, and reopen.
- Early submission, unsubmission, deadline locking, and drawing persistence.
- Session reconnection that preserves identity, assignment, drawing, and deadlines.
- Host-controlled reveal with randomized order, drawing-first reveal, original-image reveal, and results completion.
- Automatic cleanup of expired rooms and their local media.
- WebSocket lobby, game, and reveal updates.
- Automated backend test suite covering the complete flow.

## Project Structure

```
backend/
  alembic/                 Alembic environment and migrations
  app/
    api/
      deps.py              Player token and room authentication
      routes/              Health, rooms, game, reveal, and WebSocket routes
    core/                  Settings and application errors
    db/                    SQLAlchemy base, engine, and session
    models/                ORM models and enums
    schemas/               Pydantic request/response schemas
    services/              Rooms, games, drawings, reveals, uploads, cleanup, realtime
    main.py                FastAPI app factory and cleanup lifespan
  tests/                   Permanent pytest suite
  alembic.ini
  pytest.ini
  requirements.txt
  requirements-dev.txt
frontend/
  index.html               Create/join/lobby/game/reveal interface
  css/style.css            Responsive game styling
  js/                      API client, session storage, game and reveal controller
netlify.toml               Static frontend deployment configuration
.env.example               Environment variable template
```

## Prerequisites

- Python 3.11+ (3.12 recommended)
- A [Neon](https://neon.tech) PostgreSQL database
- Node.js is not required for the app. It is only needed if you use external browser tooling.

## Setup

1. Create and activate a virtual environment:

   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Install runtime dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

3. Create your local environment file from the template (skip if `.env` already exists):

   ```powershell
   Copy-Item ..\.env.example ..\.env
   ```

4. Set `DATABASE_URL` in `.env` to your Neon connection string. The pooled connection string is recommended. Both `postgresql://` and `postgresql+psycopg://` URLs are accepted.

## Database Migrations

Run Alembic from `backend/`. It loads the repository-root `.env`.

```powershell
alembic upgrade head
```

Useful commands:

```powershell
alembic current
alembic check
alembic revision --autogenerate -m "describe the change"
alembic downgrade -1
```

Migrations create all PRD entities plus lobby and game-flow fields.

## Run the Backend

From `backend/`:

```powershell
uvicorn app.main:app --reload
```

- API root: <http://127.0.0.1:8000/>
- Health: <http://127.0.0.1:8000/api/health>
- Docs: <http://127.0.0.1:8000/docs>

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

Healthy response:

```json
{"status": "ok", "database": "ok"}
```

## Run the Frontend

Serve the static frontend:

```powershell
cd frontend
python -m http.server 5500 --bind 127.0.0.1
```

Open <http://127.0.0.1:5500>.

The API URL is configured in `frontend/index.html`:

```html
<meta name="dhiogame-api-base" content="http://127.0.0.1:8000">
```

Change it to the deployed backend URL when hosting the frontend separately.

## Automated Tests

The permanent test suite lives in `backend/tests/` and exercises the real FastAPI app and PostgreSQL schema, including WebSockets.

```powershell
cd backend
pip install -r requirements-dev.txt
alembic upgrade head
pytest -q
```

Recommended: use a dedicated test database rather than your production database:

```powershell
$env:TEST_DATABASE_URL="postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require"
pytest -q
```

The suite creates unique rooms and deletes its own rooms and uploaded files during teardown. It covers:

- Room creation, joining, readiness, host permissions, player limit, and upload validation.
- Same-image and random-assignment modes.
- Assignment privacy and reference access.
- Server-authoritative phase transitions and deadline locking.
- Drawing save, submit, unsubmit, persistence, and reconnection.
- WebSocket game progress updates.
- Reveal order, original-image reveal, reveal permissions, and completion.
- Room and media expiration cleanup.

Note: tests run against a remote PostgreSQL/Neon database can take several minutes because each request crosses the network. A local Postgres instance is faster.

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes | — | Neon PostgreSQL connection string. Never commit real credentials. |
| `TEST_DATABASE_URL` | No | — | Optional test database override used by `pytest`. |
| `APP_NAME` | No | `DhioGame API` | Application title. |
| `ENVIRONMENT` | No | `development` | Deployment environment label. |
| `DEBUG` | No | `false` | FastAPI debug mode. |
| `CORS_ORIGINS` | No | `http://localhost:5500,http://127.0.0.1:5500` | Comma-separated allowed frontend origins. |
| `ROOM_TTL_HOURS` | No | `24` | Room lifetime. Completed rooms get a fresh 24-hour window. |
| `ROOM_CLEANUP_INTERVAL_SECONDS` | No | `300` | How often expired rooms are purged. |
| `MAX_UPLOAD_SIZE_BYTES` | No | `5242880` | Maximum reference image size (5 MB). |
| `MAX_DRAWING_DATA_BYTES` | No | `2000000` | Maximum serialized drawing payload. |
| `UPLOAD_DIR` | No | `backend/uploads` | Local temporary upload directory. |

`.env` is git-ignored. Only `.env.example` is committed.

## Game Flow

1. Host creates a room and uploads the required reference images.
2. Players join with the room code; the host starts the game.
3. `IMAGE_VIEWING`: every player sees their private reference and a synchronized countdown.
4. `DRAWING`: each player has an independent canvas and autosaved drawing data.
5. Players can submit early, reopen while time remains, and resubmit.
6. When the drawing deadline or host-ended timer is reached, all drawings lock.
7. `DRAWING_COMPLETED`: the host starts the reveal.
8. `REVEAL_DRAWING`: a drawing and nickname appear.
9. `REVEAL_ORIGINAL`: the host reveals the matching original beside the drawing.
10. The host advances through the randomized order until `RESULTS_COMPLETED`.
11. Completed rooms expire 24 hours later; abandoned rooms expire 24 hours after creation.

Assignments are never included in public state. The original image is only available after the host reveals it for the current player.

## WebSocket

```
GET /api/ws/rooms/{room_code}?token=<session-token>
```

Server messages:

- `{"type": "lobby_state", "state": {...}}`
- `{"type": "game_state", "state": {...}}`
- `{"type": "reveal_state", "state": {...}}`
- `{"type": "pong"}`

Clients may send `ping`. REST actions are authenticated with:

```http
Authorization: Bearer <session-token>
```

## API Overview

| Method | Path | Access | Purpose |
|---|---|---|---|
| `POST` | `/api/rooms` | Public | Create room |
| `POST` | `/api/rooms/join` | Public | Join room |
| `GET` | `/api/rooms/{code}` | Player | Lobby state |
| `POST` | `/api/rooms/{code}/ready` | Player | Set readiness |
| `PATCH` | `/api/rooms/{code}/settings` | Host | Update game settings |
| `GET/POST` | `/api/rooms/{code}/images` | Host | List/upload reference images |
| `GET/DELETE` | `/api/rooms/{code}/images/{id}` | Host | Read/delete reference image |
| `POST` | `/api/rooms/{code}/game/start` | Host | Start game |
| `GET` | `/api/rooms/{code}/game` | Player | Game state |
| `POST` | `/api/rooms/{code}/game/sync` | Player | Sync/advance phase at deadline |
| `POST` | `/api/rooms/{code}/game/finish-drawing` | Host | End drawing early |
| `GET` | `/api/rooms/{code}/game/reference` | Player | Private viewing reference |
| `GET/PUT` | `/api/rooms/{code}/drawing` | Player | Read/autosave drawing |
| `POST` | `/api/rooms/{code}/drawing/submit` | Player | Submit early |
| `POST` | `/api/rooms/{code}/drawing/unsubmit` | Player | Reopen while time remains |
| `POST` | `/api/rooms/{code}/reveal/start` | Host | Start randomized reveal |
| `GET` | `/api/rooms/{code}/reveal` | Player | Current reveal state |
| `POST` | `/api/rooms/{code}/reveal/original` | Host | Reveal the original |
| `POST` | `/api/rooms/{code}/reveal/next` | Host | Advance/reveal complete |
| `GET` | `/api/rooms/{code}/reveal/reference` | Player | Current original after reveal |
| `GET` | `/api/health` | Public | API/database health |

## Deployment Readiness

### Frontend on Netlify

A root `netlify.toml` publishes `frontend/` as a static site. Steps:

1. Push the repository to GitHub.
2. Create a Netlify site from the repository.
3. Netlify uses `netlify.toml` automatically; no build command is required.
4. Edit `frontend/index.html` and set the `dhiogame-api-base` meta tag to the public backend URL.
5. Add the Netlify origin to backend `CORS_ORIGINS`.

### Backend hosting

Use an always-on VM or container host that supports WebSockets:

1. Install Python 3.11+ and the dependencies from `backend/requirements.txt`.
2. Set production environment variables, especially `DATABASE_URL`, `CORS_ORIGINS`, and `UPLOAD_DIR`.
3. Run `alembic upgrade head` from `backend/` before starting.
4. Start Uvicorn behind a reverse proxy such as Nginx or Caddy:
   `uvicorn app.main:app --host 0.0.0.0 --port 8000`
5. Enable WebSocket proxying and sufficient timeouts in the reverse proxy.
6. Persist `UPLOAD_DIR` on durable storage. The current implementation uses local filesystem storage; production object storage remains an external follow-up.
7. Run a single worker until a shared WebSocket pub/sub layer is added. In-memory room connections do not work across multiple workers.
8. Keep the cleanup loop enabled so expired rooms and local media are deleted.

### Security notes

- Session tokens are high-entropy and stored only as SHA-256 hashes.
- Host-only actions are validated server-side.
- Assignments are private; public state never includes image IDs or storage keys.
- Original images are only served during `REVEAL_ORIGINAL`.
- Uploads are validated as JPG/PNG/WEBP, limited to 5 MB, and stored with generated keys.
- Drawing payloads are validated and size-limited.
- `.env` and `backend/uploads/` are git-ignored.
- WebSocket tokens are passed as query parameters for browser compatibility; avoid logging full WebSocket URLs in production.

## Manual Test Checklist

1. Create a room, join from a second browser window, and confirm live player/readiness updates.
2. Upload the required images and start same-image mode.
3. Confirm both players see the same reference and a synchronized viewing countdown.
4. Draw with brush, color, size, eraser, undo, redo, and clear.
5. Submit, reopen, and resubmit.
6. Refresh a player tab mid-drawing and confirm identity, drawing, and deadline are preserved.
7. Finish drawing and verify all drawings lock.
8. Start the reveal, confirm randomized order, reveal originals, and advance to completion.
9. Confirm guests cannot start/advance the reveal or modify drawings after reveal starts.
10. Run random-assignment mode with distinct images and verify each player sees only their own reference.
11. Test unlimited drawing and host-ended completion.
12. Resize to mobile width and confirm the lobby, canvas, and reveal are responsive.
13. Run `pytest -q` from `backend/` and confirm the full suite passes.

## Manual Follow-up

- Use a dedicated database for `pytest`; the default fallback uses `DATABASE_URL`.
- Configure the production backend URL in `frontend/index.html` before deploying to Netlify.
- Add object storage and automatic media cleanup there if local volume storage is not acceptable.
- Add shared WebSocket pub/sub before scaling the backend beyond one worker.
- Configure HTTPS/WSS and secure production credentials through the hosting provider.
