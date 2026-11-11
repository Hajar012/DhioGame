from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.session import get_db
from app.models import ConnectionStatus
from app.services import realtime, rooms

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])


async def _reject(
    websocket: WebSocket, code: int, reason: str
) -> None:
    await websocket.accept()
    await websocket.close(code=code, reason=reason)


@router.websocket("/rooms/{room_code}")
async def room_websocket(
    websocket: WebSocket,
    room_code: str,
    token: str | None = None,
    db: Session = Depends(get_db),
) -> None:
    room = rooms.get_room_by_code(db, room_code)
    if room is None:
        await _reject(websocket, 4404, "Room not found")
        return

    try:
        rooms.ensure_room_accessible(room)
        if not token:
            raise AppError(4401, "A player session token is required")
        player = rooms.get_player_by_token(db, room.id, token)
        if player is None:
            raise AppError(4401, "Invalid or expired session token")
    except AppError as exc:
        close_code = exc.status_code if 4000 <= exc.status_code <= 4999 else 1008
        await _reject(websocket, close_code, exc.detail)
        return

    await realtime.manager.connect(room.join_code, player.id, websocket)

    player.connection_status = ConnectionStatus.ONLINE
    player.last_seen_at = datetime.now(timezone.utc)
    db.commit()
    await realtime.broadcast_room_state(room.join_code)

    try:
        while True:
            message = await websocket.receive_text()
            if message.strip() == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        await realtime.manager.disconnect(
            room.join_code, player.id, websocket
        )
        if not realtime.manager.is_connected(room.join_code, player.id):
            try:
                player.connection_status = ConnectionStatus.OFFLINE
                player.last_seen_at = datetime.now(timezone.utc)
                db.commit()
                await realtime.broadcast_room_state(room.join_code)
            except Exception:
                logger.exception("Failed to mark player offline")
