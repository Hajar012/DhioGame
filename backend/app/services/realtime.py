from __future__ import annotations

import asyncio
import logging
import os
import uuid

from fastapi import BackgroundTasks, WebSocket

from app.db.session import SessionLocal
from app.models import GamePhase
from app.services import games, reveals
from app.services.lobby import build_room_state
from app.services.rooms import get_room_by_code

logger = logging.getLogger("uvicorn.error")

REVEAL_PHASES = {
    GamePhase.REVEAL_DRAWING,
    GamePhase.REVEAL_ORIGINAL,
    GamePhase.RESULTS_COMPLETED,
}


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


async def broadcast_game_state(room_code: str) -> None:
    with SessionLocal() as db:
        room = get_room_by_code(db, room_code)
        if room is None:
            return
        game = games.get_current_game(db, room)
        if game is None:
            return
        games.sync_game_state(db, game)
        state = games.build_game_state(db, room, game)

    await manager.broadcast(
        room.join_code,
        {"type": "game_state", "state": state.model_dump(mode="json")},
    )


def queue_game_state(background_tasks: BackgroundTasks, room_code: str) -> None:
    background_tasks.add_task(broadcast_game_state, room_code)


async def broadcast_reveal_state(room_code: str) -> None:
    with SessionLocal() as db:
        room = get_room_by_code(db, room_code)
        if room is None:
            return
        game = games.get_current_game(db, room)
        if game is None or game.current_phase not in REVEAL_PHASES:
            return
        reveal = reveals.get_reveal(db, game)
        if reveal is None:
            return
        state = reveals.build_reveal_state(db, game, reveal)

    await manager.broadcast(
        room.join_code,
        {"type": "reveal_state", "state": state.model_dump(mode="json")},
    )


def queue_reveal_state(
    background_tasks: BackgroundTasks, room_code: str
) -> None:
    background_tasks.add_task(broadcast_reveal_state, room_code)


async def game_phase_loop(interval_seconds: float = 1.0) -> None:
    heartbeat_interval = 60.0
    heartbeat_elapsed = 0.0

    logger.info(
        "Game phase loop started pid=%s instance=%s commit=%s interval=%ss",
        os.getpid(),
        os.environ.get("RENDER_INSTANCE_ID", "unknown"),
        os.environ.get("RENDER_GIT_COMMIT", "unknown"),
        interval_seconds,
    )

    while True:
        changed_rooms: list[str] = []
        try:
            with SessionLocal() as db:
                changed_rooms = games.sync_active_games(db)
            for room_code in changed_rooms:
                await broadcast_game_state(room_code)
            if changed_rooms:
                logger.info(
                    "Game phase loop advanced rooms pid=%s rooms=%s",
                    os.getpid(),
                    changed_rooms,
                )
        except Exception:
            logger.exception(
                "Game phase synchronization failed pid=%s",
                os.getpid(),
            )

        heartbeat_elapsed += interval_seconds
        if heartbeat_elapsed >= heartbeat_interval:
            heartbeat_elapsed = 0.0
            logger.info(
                "Game phase loop heartbeat pid=%s changed_rooms=%s",
                os.getpid(),
                changed_rooms,
            )

        await asyncio.sleep(interval_seconds)
