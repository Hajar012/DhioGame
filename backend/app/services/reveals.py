from __future__ import annotations

import secrets
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models import (
    Assignment,
    Drawing,
    DrawingStatus,
    Game,
    GameMode,
    GamePhase,
    Player,
    ReferenceImage,
    Reveal,
    Room,
    RoomStatus,
)
from app.schemas.reveal import RevealPlayer, RevealState
from app.services import drawings, games


def get_reveal(db: Session, game: Game) -> Reveal | None:
    return db.scalar(
        select(Reveal)
        .where(Reveal.game_id == game.id)
        .execution_options(populate_existing=True)
    )


def get_reveal_or_404(db: Session, game: Game) -> Reveal:
    reveal = get_reveal(db, game)
    if reveal is None:
        raise AppError(404, "The reveal has not started")
    return reveal


def get_reveal_order(reveal: Reveal) -> list[UUID]:
    order: list[UUID] = []
    for raw_id in reveal.reveal_order or []:
        try:
            order.append(UUID(str(raw_id)))
        except ValueError:
            continue
    return order


def _lock_game(db: Session, game: Game) -> Game:
    locked_game = db.scalar(
        select(Game)
        .where(Game.id == game.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if locked_game is None:
        raise AppError(404, "Game not found")
    return locked_game


def _lock_reveal(db: Session, game: Game) -> Reveal:
    reveal = db.scalar(
        select(Reveal)
        .where(Reveal.game_id == game.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if reveal is None:
        raise AppError(409, "The reveal has not started")
    return reveal


def start_reveal(db: Session, room: Room, game: Game) -> Reveal:
    locked_game = _lock_game(db, game)
    if locked_game.current_phase != GamePhase.DRAWING_COMPLETED:
        raise AppError(
            409,
            "Finish the drawing phase before starting the reveal",
        )
    if get_reveal(db, locked_game) is not None:
        raise AppError(409, "The reveal has already started")

    players = db.scalars(
        select(Player)
        .where(Player.room_id == room.id)
        .order_by(Player.created_at)
    ).all()
    if not players:
        raise AppError(409, "There are no players to reveal")

    reveal_order = [str(player.id) for player in players]
    secrets.SystemRandom().shuffle(reveal_order)

    reveal = Reveal(
        game_id=locked_game.id,
        reveal_order=reveal_order,
        current_index=0,
        started_at=games.utcnow(),
    )
    db.add(reveal)
    locked_game.current_phase = GamePhase.REVEAL_DRAWING
    db.commit()
    db.refresh(reveal)
    return reveal


def reveal_original(db: Session, game: Game) -> Reveal:
    locked_game = _lock_game(db, game)
    if locked_game.current_phase == GamePhase.REVEAL_ORIGINAL:
        return _lock_reveal(db, locked_game)
    if locked_game.current_phase != GamePhase.REVEAL_DRAWING:
        raise AppError(409, "The original image is not ready to reveal")
    reveal = _lock_reveal(db, locked_game)
    locked_game.current_phase = GamePhase.REVEAL_ORIGINAL
    db.commit()
    db.refresh(reveal)
    return reveal


def next_reveal(db: Session, room: Room, game: Game) -> Reveal:
    locked_game = _lock_game(db, game)
    if locked_game.current_phase != GamePhase.REVEAL_ORIGINAL:
        raise AppError(409, "Reveal the original image before continuing")

    reveal = _lock_reveal(db, locked_game)
    order = get_reveal_order(reveal)
    next_index = reveal.current_index + 1
    now = games.utcnow()

    if next_index >= len(order):
        reveal.current_index = len(order)
        locked_game.current_phase = GamePhase.RESULTS_COMPLETED
        locked_game.completed_at = now

        locked_room = db.scalar(
            select(Room).where(Room.id == room.id).with_for_update()
        )
        if locked_room is not None:
            locked_room.status = RoomStatus.COMPLETED
            locked_room.expires_at = now + timedelta(
                hours=get_settings().room_ttl_hours
            )
    else:
        reveal.current_index = next_index
        locked_game.current_phase = GamePhase.REVEAL_DRAWING

    db.commit()
    db.refresh(reveal)
    return reveal


def build_reveal_state(
    db: Session, game: Game, reveal: Reveal
) -> RevealState:
    order = get_reveal_order(reveal)
    current_player: RevealPlayer | None = None

    if (
        game.current_phase in {GamePhase.REVEAL_DRAWING, GamePhase.REVEAL_ORIGINAL}
        and 0 <= reveal.current_index < len(order)
    ):
        player_id = order[reveal.current_index]
        player = db.get(Player, player_id)
        if player is not None:
            drawing = db.scalar(
                select(Drawing).where(
                    Drawing.game_id == game.id,
                    Drawing.player_id == player.id,
                )
            )
            current_player = RevealPlayer(
                player_id=player.id,
                nickname=player.nickname,
                drawing_status=(
                    drawing.status
                    if drawing is not None
                    else DrawingStatus.LOCKED
                ),
                drawing_data=(
                    drawings.parse_drawing_data(drawing)
                    if drawing is not None
                    else None
                ),
            )

    return RevealState(
        id=reveal.id,
        game_id=game.id,
        phase=game.current_phase,
        current_index=reveal.current_index,
        total_players=len(order),
        current_player=current_player,
        original_revealed=game.current_phase == GamePhase.REVEAL_ORIGINAL,
        server_time=games.utcnow(),
    )


def get_current_reference_image(
    db: Session, room: Room, game: Game, reveal: Reveal
) -> ReferenceImage:
    if game.current_phase != GamePhase.REVEAL_ORIGINAL:
        raise AppError(403, "The original image has not been revealed")

    order = get_reveal_order(reveal)
    if not (0 <= reveal.current_index < len(order)):
        raise AppError(404, "There is no current reveal")

    if game.mode == GameMode.SAME_IMAGE:
        image = db.scalar(
            select(ReferenceImage)
            .where(ReferenceImage.room_id == room.id)
            .order_by(ReferenceImage.created_at)
            .limit(1)
        )
    else:
        image = db.scalar(
            select(ReferenceImage)
            .join(
                Assignment,
                Assignment.reference_image_id == ReferenceImage.id,
            )
            .where(
                Assignment.game_id == game.id,
                Assignment.player_id == order[reveal.current_index],
            )
        )

    if image is None:
        raise AppError(404, "Original reference image not found")
    return image
