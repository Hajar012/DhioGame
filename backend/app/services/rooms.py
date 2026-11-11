from __future__ import annotations

import secrets
import string
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models import (
    ConnectionStatus,
    GameMode,
    Player,
    PlayerRole,
    ReferenceImage,
    Room,
    RoomStatus,
)
from app.schemas.rooms import RoomCreate, RoomSettings, RoomSettingsUpdate
from app.services.tokens import generate_session_token, hash_session_token

MIN_PLAYERS = 2
MAX_PLAYERS = 10
JOIN_CODE_LENGTH = 6
JOIN_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def normalize_join_code(code: str) -> str:
    return code.strip().upper()


def get_room_by_code(
    db: Session, code: str, *, for_update: bool = False
) -> Room | None:
    statement = select(Room).where(Room.join_code == normalize_join_code(code))
    if for_update:
        statement = statement.with_for_update()
    return db.scalar(statement)


def generate_join_code(db: Session) -> str:
    for _ in range(20):
        code = "".join(
            secrets.choice(JOIN_CODE_ALPHABET) for _ in range(JOIN_CODE_LENGTH)
        )
        exists = db.scalar(select(Room.id).where(Room.join_code == code))
        if exists is None:
            return code
    raise AppError(503, "Could not allocate a room code. Please try again.")


def ensure_room_accessible(room: Room | None) -> None:
    if room is None:
        raise AppError(404, "Room not found")
    now = datetime.now(timezone.utc)
    if room.status == RoomStatus.EXPIRED:
        raise AppError(410, "This room has expired")
    if room.expires_at is not None and room.expires_at <= now:
        raise AppError(410, "This room has expired")


def ensure_waiting(room: Room) -> None:
    if room.status != RoomStatus.WAITING:
        raise AppError(409, "This room is no longer accepting lobby changes")


def is_host(room: Room, player: Player) -> bool:
    return player.role == PlayerRole.HOST or room.host_id == player.id


def require_host(room: Room, player: Player) -> None:
    if not is_host(room, player):
        raise AppError(403, "Only the host can perform this action")


def get_player_by_token(
    db: Session, room_id, token: str
) -> Player | None:
    if not token:
        return None
    token_hash = hash_session_token(token)
    return db.scalar(
        select(Player).where(
            Player.room_id == room_id,
            Player.session_token_hash == token_hash,
        )
    )


def create_room(
    db: Session, payload: RoomCreate
) -> tuple[Room, Player, str]:
    settings = get_settings()
    join_code = generate_join_code(db)
    now = datetime.now(timezone.utc)
    room = Room(
        join_code=join_code,
        status=RoomStatus.WAITING,
        settings=payload.settings.model_dump(mode="json"),
        expires_at=now + timedelta(hours=settings.room_ttl_hours),
    )
    db.add(room)

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(503, "Could not create the room. Please try again.") from exc

    token = generate_session_token()
    player = Player(
        room_id=room.id,
        nickname=payload.nickname,
        role=PlayerRole.HOST,
        connection_status=ConnectionStatus.OFFLINE,
        session_token_hash=hash_session_token(token),
        is_ready=False,
    )
    db.add(player)
    db.flush()

    room.host_id = player.id
    db.commit()
    db.refresh(room)
    db.refresh(player)
    return room, player, token


def join_room(
    db: Session, room_code: str, nickname: str
) -> tuple[Room, Player, str]:
    room = get_room_by_code(db, room_code, for_update=True)
    ensure_room_accessible(room)
    ensure_waiting(room)

    player_count = (
        db.scalar(
            select(func.count())
            .select_from(Player)
            .where(Player.room_id == room.id)
        )
        or 0
    )
    if player_count >= MAX_PLAYERS:
        raise AppError(409, "This room is full")

    duplicate = db.scalar(
        select(Player.id).where(
            Player.room_id == room.id,
            func.lower(Player.nickname) == nickname.strip().lower(),
        )
    )
    if duplicate is not None:
        raise AppError(409, "That nickname is already in use in this room")

    token = generate_session_token()
    player = Player(
        room_id=room.id,
        nickname=nickname.strip(),
        role=PlayerRole.PLAYER,
        connection_status=ConnectionStatus.OFFLINE,
        session_token_hash=hash_session_token(token),
        is_ready=False,
    )
    db.add(player)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(409, "That nickname is already in use in this room") from exc

    db.refresh(room)
    db.refresh(player)
    return room, player, token


def set_ready(db: Session, room: Room, player: Player, is_ready: bool) -> None:
    ensure_waiting(room)
    player.is_ready = is_ready
    player.last_seen_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(player)


def update_settings(
    db: Session, room: Room, update: RoomSettingsUpdate
) -> RoomSettings:
    ensure_waiting(room)
    current = RoomSettings.model_validate(room.settings or {})
    changes = update.model_dump(exclude_unset=True, mode="json")
    new_settings = RoomSettings.model_validate(
        {**current.model_dump(mode="json"), **changes}
    )

    if new_settings.mode == GameMode.SAME_IMAGE:
        image_count = (
            db.scalar(
                select(func.count())
                .select_from(ReferenceImage)
                .where(ReferenceImage.room_id == room.id)
            )
            or 0
        )
        if image_count > 1:
            raise AppError(
                409,
                "Delete extra images before switching to same-image mode",
            )

    room.settings = new_settings.model_dump(mode="json")
    db.commit()
    db.refresh(room)
    return new_settings
