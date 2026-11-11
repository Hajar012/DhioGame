# DhioGame

Real-time multiplayer drawing game: players join private rooms, draw from reference images, and reveal results together. See [`PRD.md`](./PRD.md) for the product requirements.

The current milestone includes the backend foundation and the live lobby: private rooms, join codes, player sessions, readiness, host-controlled settings, reference image uploads, WebSocket lobby updates, and a responsive create/join/lobby frontend. Drawing, gameplay phases, and the results reveal are not implemented yet.

## Project Structure

```
backend/
  alembic/              Alembic environment and migrations
  app/
    api/
      deps.py           Token/room authentication dependencies
      routes/           Health, rooms, and WebSocket routes
    core/               Settings and application errors
    db/                 SQLAlchemy base, engine, and session
    models/             ORM models and enums
    schemas/            Pydantic request/response schemas
    services/           Rooms, lobby state, uploads, tokens, realtime
    main.py             FastAPI application factory
  alembic.ini
  requirements.txt
frontend/
  index.html            Create/join/lobby interface
  css/style.css         Responsive styling
  js/                   API client, session storage, lobby controller
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
# Apply all migrations
alembic upgrade head

# Create a new migration after changing models
alembic revision --autogenerate -m "describe the change"
alembic upgrade head

# Roll back the most recent migration
alembic downgrade -1
```

Migrations currently create the PRD entities (`rooms`, `players`, `games`, `reference_images`, `assignments`, `drawings`, `reveals`) plus lobby fields for readiness and room-scoped reference images.

## Run the Backend

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

If the database cannot be reached, the endpoint returns HTTP `503`.

## Run the Frontend

The frontend is plain HTML, CSS, and JavaScript. Serve it with any static file server; for local development:

```powershell
cd frontend
python -m http.server 5500 --bind 127.0.0.1
```

Open <http://127.0.0.1:5500>. The default CORS configuration allows this origin.

The API base URL is configured in `frontend/index.html`:

```html
<meta name="dhiogame-api-base" content="http://127.0.0.1:8000">
```

Change it to your deployed backend URL when hosting the frontend separately (for example, on Netlify).

## Lobby Features

- Create a private room; the creator becomes the host.
- Join by six-character room code with a nickname.
- Room capacity is enforced server-side at 10 players; the PRD minimum is 2 players.
- Nicknames are unique per room (case-insensitive).
- Players receive a secure session token and restore their session after a page refresh.
- Players can toggle ready status; the lobby shows online/offline connection state.
- The host controls game mode, reference viewing duration, and drawing duration. All changes are synchronized over WebSocket.
- The host uploads JPG, PNG, or WEBP reference images up to 5 MB each.
  - Same-image mode accepts exactly one image.
  - Random-assignment mode accepts one image per current player.
- Uploaded image previews and deletion are host-only.
- Rooms expire after 24 hours by default and their database rows cascade on deletion.

REST actions are authenticated with the player token:

```http
Authorization: Bearer <session-token>
```

The WebSocket endpoint is:

```
GET /api/ws/rooms/{room_code}?token=<session-token>
```

It sends `{"type": "lobby_state", "state": {...}}` messages whenever players, readiness, settings, uploads, or connection state change. Clients may send `ping` to receive `{"type": "pong"}`.

## API Overview

| Method | Path | Access | Purpose |
|---|---|---|---|
| `POST` | `/api/rooms` | Public | Create a room and host player |
| `POST` | `/api/rooms/join` | Public | Join by room code |
| `GET` | `/api/rooms/{room_code}` | Player token | Read current lobby state |
| `POST` | `/api/rooms/{room_code}/ready` | Player token | Set readiness |
| `PATCH` | `/api/rooms/{room_code}/settings` | Host only | Update mode/durations |
| `GET` | `/api/rooms/{room_code}/images` | Host only | List uploaded images |
| `POST` | `/api/rooms/{room_code}/images` | Host only | Upload one image |
| `GET` | `/api/rooms/{room_code}/images/{id}/content` | Host only | Fetch image content |
| `DELETE` | `/api/rooms/{room_code}/images/{id}` | Host only | Delete an image |
| `GET` | `/api/health` | Public | API and database health |

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes | — | Neon PostgreSQL connection string. Never commit real credentials. |
| `APP_NAME` | No | `DhioGame API` | Application title shown in the docs. |
| `ENVIRONMENT` | No | `development` | Deployment environment label. |
| `DEBUG` | No | `false` | Enables FastAPI debug mode. |
| `CORS_ORIGINS` | No | `http://localhost:5500,http://127.0.0.1:5500` | Comma-separated allowed frontend origins. |
| `ROOM_TTL_HOURS` | No | `24` | Room lifetime before access is rejected. |
| `MAX_UPLOAD_SIZE_BYTES` | No | `5242880` | Maximum reference image size (5 MB). |
| `UPLOAD_DIR` | No | `backend/uploads` | Local directory for temporary reference image storage. |

`.env` is git-ignored. Only `.env.example` is committed.

## Data Model

- **Room** — join code, host, status, lobby settings, expiry.
- **Player** — room membership, nickname, role, readiness, connection status, hashed session token.
- **Game** — room, mode, current phase, durations, timestamps (reserved for gameplay).
- **ReferenceImage** — room-scoped upload with optional future game association.
- **Assignment** — one reference image per player per game (unique, no duplicates).
- **Drawing** — player/game canvas data and submission status.
- **Reveal** — randomized reveal order and current index for a game.

## Testing Checklist

1. Start the backend and frontend.
2. Create a room in one browser window and copy the code.
3. Open a second window (or incognito) and join with the code.
4. Confirm both lobbies update player lists and online status in real time.
5. Toggle ready in one window and confirm the other updates.
6. Change settings as the host and confirm guests receive them live.
7. Upload one image per player in random mode (or one image in same-image mode) and confirm all lobbies update the upload count.
8. Confirm guests cannot change settings, upload images, or open the host image list.
9. Refresh a player tab and confirm the session is restored.
10. Resize to a mobile viewport and confirm the lobby has no horizontal overflow.

## Manual Follow-up

- Run `alembic upgrade head` against the target database before starting the API.
- Configure the production `DATABASE_URL` and `CORS_ORIGINS` on the backend host; never upload `.env`.
- Reference images are stored on the local filesystem for this milestone. Production object storage and automatic cleanup are still pending.
- WebSocket connections are tracked in process memory. Run a single backend worker until a shared pub/sub layer is added for multi-worker deployments.
- Drawing, game phases, timers, assignments, and the reveal flow remain for later milestones.
