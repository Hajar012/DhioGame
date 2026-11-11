from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import GameMode, Player, ReferenceImage, Room
from app.schemas.rooms import (
    PlayerResponse,
    ReferenceImageResponse,
    RoomSettings,
    RoomState,
)
from app.services.rooms import MAX_PLAYERS, MIN_PLAYERS, is_host, normalize_join_code


def required_image_count(mode: GameMode, player_count: int) -> int:
    if mode == GameMode.SAME_IMAGE:
        return 1
    return max(player_count, 1)


def count_uploaded_images(db: Session, room_id) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(ReferenceImage)
            .where(ReferenceImage.room_id == room_id)
        )
        or 0
    )


def player_to_response(room: Room, player: Player) -> PlayerResponse:
    return PlayerResponse(
        id=player.id,
        nickname=player.nickname,
        role=player.role,
        is_ready=player.is_ready,
        connection_status=player.connection_status,
        is_host=is_host(room, player),
    )


def build_room_state(db: Session, room: Room) -> RoomState:
    players = db.scalars(
        select(Player)
        .where(Player.room_id == room.id)
        .order_by(Player.created_at)
    ).all()
    settings = RoomSettings.model_validate(room.settings or {})
    uploaded = count_uploaded_images(db, room.id)
    required = required_image_count(settings.mode, len(players))

    return RoomState(
        code=normalize_join_code(room.join_code),
        status=room.status,
        settings=settings,
        players=[player_to_response(room, player) for player in players],
        player_count=len(players),
        min_players=MIN_PLAYERS,
        max_players=MAX_PLAYERS,
        ready_count=sum(1 for player in players if player.is_ready),
        uploaded_images=uploaded,
        required_images=required,
        uploads_complete=uploaded >= required,
        created_at=room.created_at,
        expires_at=room.expires_at,
    )


def to_image_response(
    image: ReferenceImage, room_code: str
) -> ReferenceImageResponse:
    return ReferenceImageResponse(
        id=image.id,
        original_filename=image.original_filename,
        content_type=image.content_type,
        file_size=image.file_size,
        created_at=image.created_at,
        content_url=(
            f"/api/rooms/{normalize_join_code(room_code)}/images/"
            f"{image.id}/content"
        ),
    )
