from __future__ import annotations

import uuid

from fastapi import BackgroundTasks, WebSocket

from app.db.session import SessionLocal
from app.services.lobby import build_room_state
from app.services.rooms import get_room_by_code


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, dict[uuid.UUID, WebSocket]] = {}

    async def connect(
        self, room_code: str, player_id: uuid.UUID, websocket: WebSocket
    ) -> None:
        await websocket.accept()
        room_connections = self._connections.setdefault(room_code, {})
        previous = room_connections.get(player_id)
        room_connections[player_id] = websocket
        if previous is not None and previous is not websocket:
            try:
                await previous.close(code=4001)
            except Exception:
                pass

    async def disconnect(
        self, room_code: str, player_id: uuid.UUID, websocket: WebSocket
    ) -> None:
        room_connections = self._connections.get(room_code)
        if not room_connections:
            return
        if room_connections.get(player_id) is websocket:
            room_connections.pop(player_id, None)
        if not room_connections:
            self._connections.pop(room_code, None)

    def is_connected(self, room_code: str, player_id: uuid.UUID) -> bool:
        return player_id in self._connections.get(room_code, {})

    async def broadcast(self, room_code: str, message: dict) -> None:
        room_connections = self._connections.get(room_code)
        if not room_connections:
            return

        stale: list[tuple[uuid.UUID, WebSocket]] = []
        for player_id, websocket in list(room_connections.items()):
            try:
                await websocket.send_json(message)
            except Exception:
                stale.append((player_id, websocket))

        for player_id, websocket in stale:
            await self.disconnect(room_code, player_id, websocket)


manager = ConnectionManager()


async def broadcast_room_state(room_code: str) -> None:
    with SessionLocal() as db:
        room = get_room_by_code(db, room_code)
        if room is None:
            return
        state = build_room_state(db, room)

    await manager.broadcast(
        room.join_code,
        {"type": "lobby_state", "state": state.model_dump(mode="json")},
    )


def queue_room_state(background_tasks: BackgroundTasks, room_code: str) -> None:
    background_tasks.add_task(broadcast_room_state, room_code)
