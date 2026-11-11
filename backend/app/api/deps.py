from dataclasses import dataclass

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.session import get_db
from app.models import Player, Room
from app.services import rooms

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class RoomContext:
    room: Room
    player: Player
    is_host: bool


def get_room_context(
    room_code: str,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> RoomContext:
    room = rooms.get_room_by_code(db, room_code)
    if room is None:
        raise AppError(404, "Room not found")
    rooms.ensure_room_accessible(room)

    if credentials is None or not credentials.credentials:
        raise AppError(401, "A player session token is required")

    player = rooms.get_player_by_token(db, room.id, credentials.credentials)
    if player is None:
        raise AppError(401, "Invalid or expired session token")

    return RoomContext(
        room=room,
        player=player,
        is_host=rooms.is_host(room, player),
    )
