from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import (
    Assignment,
    ConnectionStatus,
    Drawing,
    DrawingStatus,
    Game,
    GameMode,
    GamePhase,
    Player,
    ReferenceImage,
    Room,
    RoomStatus,
)
from app.schemas.game import GamePlayerProgress, GameState
from app.schemas.rooms import RoomSettings
from app.services.lobby import required_image_count
from app.services.rooms import (
    MIN_PLAYERS,
    ensure_waiting,
    normalize_join_code,
)

LOCKED_PHASES = {
    GamePhase.DRAWING_COMPLETED,
    GamePhase.REVEAL_DRAWING,
    GamePhase.REVEAL_ORIGINAL,
    GamePhase.RESULTS_COMPLETED,
    GamePhase.EXPIRED,
}

VIEWING_LOAD_TIMEOUT_SECONDS = 30


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_current_game(
    db: Session, room: Room, *, for_update: bool = False
) -> Game | None:
    statement = (
        select(Game)
        .where(Game.room_id == room.id)
        .order_by(Game.created_at.desc())
        .limit(1)
    )
    if for_update:
        statement = statement.with_for_update()
    statement = statement.execution_options(populate_existing=True)
    return db.scalar(statement)


def start_game(db: Session, room: Room) -> Game:
    locked_room = db.scalar(
        select(Room).where(Room.id == room.id).with_for_update()
    )
    if locked_room is None:
        raise AppError(404, "Room not found")
    ensure_waiting(locked_room)

    players = db.scalars(
        select(Player)
        .where(Player.room_id == locked_room.id)
        .order_by(Player.created_at)
    ).all()
    if len(players) < MIN_PLAYERS:
        raise AppError(
            409,
            f"At least {MIN_PLAYERS} players are required to start the game",
        )

    settings = RoomSettings.model_validate(locked_room.settings or {})
    images = list(
        db.scalars(
            select(ReferenceImage)
            .where(ReferenceImage.room_id == locked_room.id)
            .order_by(ReferenceImage.created_at)
        ).all()
    )
    required = required_image_count(settings.mode, len(players))
    if len(images) != required:
        if settings.mode == GameMode.SAME_IMAGE:
            message = (
                "Same-image mode requires exactly one uploaded reference image"
            )
        else:
            message = (
                "Random assignment requires exactly one image per player "
                f"({len(players)} total)"
            )
        raise AppError(409, message)

    now = utcnow()
    game = Game(
        room_id=locked_room.id,
        mode=settings.mode,
        current_phase=GamePhase.IMAGE_VIEWING,
        viewing_duration_seconds=settings.viewing_duration_seconds,
        drawing_duration_seconds=settings.drawing_duration_seconds,
        phase_started_at=None,
        phase_ends_at=None,
        started_at=now,
    )
    db.add(game)
    db.flush()

    if settings.mode == GameMode.RANDOM_ASSIGNMENT:
        shuffled_images = list(images)
        secrets.SystemRandom().shuffle(shuffled_images)
        for player, image in zip(players, shuffled_images, strict=True):
            db.add(
                Assignment(
                    game_id=game.id,
                    player_id=player.id,
                    reference_image_id=image.id,
                )
            )

    for player in players:
        db.add(
            Drawing(
                game_id=game.id,
                player_id=player.id,
                status=DrawingStatus.DRAFT,
            )
        )

    locked_room.status = RoomStatus.IN_PROGRESS
    db.commit()
    db.refresh(game)
    return game


def _lock_drawings(db: Session, game_id) -> None:
    db.execute(
        update(Drawing)
        .where(
            Drawing.game_id == game_id,
            Drawing.status != DrawingStatus.LOCKED,
        )
        .values(status=DrawingStatus.LOCKED)
    )


def _start_viewing_timer(game: Game, now: datetime) -> None:
    game.phase_started_at = now
    game.phase_ends_at = now + timedelta(
        seconds=game.viewing_duration_seconds or 0
    )


def sync_game_state(
    db: Session, game: Game, *, now: datetime | None = None
) -> bool:
    now = now or utcnow()
    locked_game = db.scalar(
        select(Game)
        .where(Game.id == game.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if locked_game is None:
        raise AppError(404, "Game not found")

    if locked_game.current_phase in LOCKED_PHASES:
        db.commit()
        return False

    changed = False

    if (
        locked_game.current_phase == GamePhase.IMAGE_VIEWING
        and locked_game.phase_ends_at is None
        and locked_game.started_at is not None
        and now
        >= locked_game.started_at
        + timedelta(seconds=VIEWING_LOAD_TIMEOUT_SECONDS)
    ):
        _start_viewing_timer(locked_game, now)
        changed = True

    if (
        locked_game.current_phase == GamePhase.IMAGE_VIEWING
        and locked_game.phase_ends_at is not None
        and now >= locked_game.phase_ends_at
    ):
        locked_game.current_phase = GamePhase.DRAWING
        locked_game.phase_started_at = now
        if locked_game.drawing_duration_seconds is None:
            locked_game.phase_ends_at = None
            locked_game.ends_at = None
        else:
            locked_game.phase_ends_at = now + timedelta(
                seconds=locked_game.drawing_duration_seconds
            )
            locked_game.ends_at = locked_game.phase_ends_at
        changed = True

    if (
        locked_game.current_phase == GamePhase.DRAWING
        and locked_game.phase_ends_at is not None
        and now >= locked_game.phase_ends_at
    ):
        locked_game.current_phase = GamePhase.DRAWING_COMPLETED
        _lock_drawings(db, locked_game.id)
        changed = True

    db.commit()
    return changed


def sync_active_games(db: Session, *, now: datetime | None = None) -> list[str]:
    now = now or utcnow()
    active_games = db.scalars(
        select(Game)
        .where(
            Game.current_phase.in_(
                [GamePhase.IMAGE_VIEWING, GamePhase.DRAWING]
            )
        )
        .execution_options(populate_existing=True)
    ).all()

    changed_room_codes: list[str] = []
    for game in active_games:
        if not sync_game_state(db, game, now=now):
            continue
        room = db.get(Room, game.room_id)
        if room is not None:
            changed_room_codes.append(room.join_code)
    return changed_room_codes


def mark_reference_loaded(
    db: Session, game: Game, player: Player
) -> tuple[Game, bool]:
    locked_game = db.scalar(
        select(Game)
        .where(Game.id == game.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if locked_game is None:
        raise AppError(404, "Game not found")
    if locked_game.current_phase != GamePhase.IMAGE_VIEWING:
        return locked_game, False

    drawing = db.scalar(
        select(Drawing)
        .where(
            Drawing.game_id == locked_game.id,
            Drawing.player_id == player.id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if drawing is None or drawing.reference_loaded_at is not None:
        return locked_game, False

    now = utcnow()
    drawing.reference_loaded_at = now
    db.flush()

    pending = db.scalar(
        select(Drawing.id)
        .where(
            Drawing.game_id == locked_game.id,
            Drawing.reference_loaded_at.is_(None),
        )
        .limit(1)
    )
    started = False
    if pending is None and locked_game.phase_ends_at is None:
        _start_viewing_timer(locked_game, now)
        started = True

    db.commit()
    db.refresh(locked_game)
    return locked_game, started


def finish_drawing(db: Session, game: Game) -> None:
    locked_game = db.scalar(
        select(Game)
        .where(Game.id == game.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if locked_game is None:
        raise AppError(404, "Game not found")
    if locked_game.current_phase != GamePhase.DRAWING:
        raise AppError(409, "Drawing is not currently active")

    locked_game.current_phase = GamePhase.DRAWING_COMPLETED
    locked_game.phase_ends_at = utcnow()
    _lock_drawings(db, locked_game.id)
    db.commit()


def build_game_state(db: Session, room: Room, game: Game) -> GameState:
    players = db.scalars(
        select(Player)
        .where(Player.room_id == room.id)
        .order_by(Player.created_at)
    ).all()
    drawings = {
        drawing.player_id: drawing
        for drawing in db.scalars(
            select(Drawing).where(Drawing.game_id == game.id)
        ).all()
    }

    progress: list[GamePlayerProgress] = []
    submitted_count = 0
    for player in players:
        drawing = drawings.get(player.id)
        status = drawing.status if drawing is not None else DrawingStatus.DRAFT
        if status in {DrawingStatus.SUBMITTED, DrawingStatus.LOCKED}:
            submitted_count += 1
        progress.append(
            GamePlayerProgress(
                player_id=player.id,
                nickname=player.nickname,
                is_connected=(
                    player.connection_status == ConnectionStatus.ONLINE
                ),
                drawing_status=status,
                has_drawing=bool(drawing and drawing.data),
            )
        )

    return GameState(
        id=game.id,
        room_code=normalize_join_code(room.join_code),
        mode=game.mode,
        phase=game.current_phase,
        viewing_duration_seconds=game.viewing_duration_seconds,
        drawing_duration_seconds=game.drawing_duration_seconds,
        phase_started_at=game.phase_started_at,
        phase_ends_at=game.phase_ends_at,
        started_at=game.started_at,
        server_time=utcnow(),
        player_count=len(players),
        submitted_count=submitted_count,
        drawings_locked=game.current_phase in LOCKED_PHASES,
        reference_available=game.current_phase == GamePhase.IMAGE_VIEWING,
        players=progress,
    )


def get_reference_image_for_player(
    db: Session, room: Room, game: Game, player: Player
) -> ReferenceImage:
    if game.current_phase != GamePhase.IMAGE_VIEWING:
        raise AppError(403, "The reference image is no longer available")

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
                Assignment.player_id == player.id,
            )
        )

    if image is None:
        raise AppError(404, "Reference image not found")
    return image
