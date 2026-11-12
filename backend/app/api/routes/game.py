from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import RoomContext, get_room_context
from app.core.errors import AppError
from app.db.session import get_db
from app.models import Game, GamePhase
from app.schemas.game import (
    DrawingMutationResponse,
    DrawingSaveRequest,
    DrawingState,
    GameState,
)
from app.services import drawings, games, images, realtime, rooms

router = APIRouter(prefix="/rooms", tags=["game"])


def _get_game_or_404(db: Session, context: RoomContext) -> Game:
    game = games.get_current_game(db, context.room)
    if game is None:
        raise AppError(404, "The game has not started")
    return game


@router.post("/{room_code}/game/start", response_model=GameState)
def start_game(
    room_code: str,
    background_tasks: BackgroundTasks,
    context: RoomContext = Depends(get_room_context),
    db: Session = Depends(get_db),
) -> GameState:
    rooms.require_host(context.room, context.player)
    game = games.start_game(db, context.room)
    state = games.build_game_state(db, context.room, game)
    realtime.queue_game_state(background_tasks, context.room.join_code)
    realtime.queue_room_state(background_tasks, context.room.join_code)
    return state


@router.get("/{room_code}/game", response_model=GameState)
def read_game(
    room_code: str,
    background_tasks: BackgroundTasks,
    context: RoomContext = Depends(get_room_context),
    db: Session = Depends(get_db),
) -> GameState:
    game = _get_game_or_404(db, context)
    changed = games.sync_game_state(db, game)
    state = games.build_game_state(db, context.room, game)
    if changed:
        realtime.queue_game_state(background_tasks, context.room.join_code)
    return state


@router.post(
    "/{room_code}/game/reference-loaded",
    response_model=GameState,
)
def mark_reference_loaded(
    room_code: str,
    background_tasks: BackgroundTasks,
    context: RoomContext = Depends(get_room_context),
    db: Session = Depends(get_db),
) -> GameState:
    game = _get_game_or_404(db, context)
    changed = games.sync_game_state(db, game)
    game, started = games.mark_reference_loaded(db, game, context.player)
    state = games.build_game_state(db, context.room, game)
    if changed or started:
        realtime.queue_game_state(background_tasks, context.room.join_code)
    return state


@router.post("/{room_code}/game/sync", response_model=GameState)
def sync_game(
    room_code: str,
    background_tasks: BackgroundTasks,
    context: RoomContext = Depends(get_room_context),
    db: Session = Depends(get_db),
) -> GameState:
    game = _get_game_or_404(db, context)
    changed = games.sync_game_state(db, game)
    state = games.build_game_state(db, context.room, game)
    if changed:
        realtime.queue_game_state(background_tasks, context.room.join_code)
    return state


@router.post("/{room_code}/game/finish-drawing", response_model=GameState)
def finish_drawing(
    room_code: str,
    background_tasks: BackgroundTasks,
    context: RoomContext = Depends(get_room_context),
    db: Session = Depends(get_db),
) -> GameState:
    rooms.require_host(context.room, context.player)
    game = _get_game_or_404(db, context)
    changed = games.sync_game_state(db, game)

    if game.current_phase == GamePhase.DRAWING:
        games.finish_drawing(db, game)
        changed = True
    elif game.current_phase != GamePhase.DRAWING_COMPLETED:
        raise AppError(409, "Drawing is not currently active")

    state = games.build_game_state(db, context.room, game)
    if changed:
        realtime.queue_game_state(background_tasks, context.room.join_code)
    return state


@router.get(
    "/{room_code}/game/reference",
    response_class=FileResponse,
)
def read_my_reference(
    room_code: str,
    background_tasks: BackgroundTasks,
    context: RoomContext = Depends(get_room_context),
    db: Session = Depends(get_db),
) -> FileResponse:
    game = _get_game_or_404(db, context)
    changed = games.sync_game_state(db, game)
    if changed:
        realtime.queue_game_state(background_tasks, context.room.join_code)

    image = games.get_reference_image_for_player(
        db, context.room, game, context.player
    )
    path = images.get_storage_path(image.storage_key)
    if not path.is_file():
        raise AppError(404, "Reference image file is missing")

    return FileResponse(
        path,
        media_type=image.content_type or "application/octet-stream",
        filename=image.original_filename or path.name,
    )


@router.get("/{room_code}/drawing", response_model=DrawingState)
def read_drawing(
    room_code: str,
    background_tasks: BackgroundTasks,
    context: RoomContext = Depends(get_room_context),
    db: Session = Depends(get_db),
) -> DrawingState:
    game = _get_game_or_404(db, context)
    changed = games.sync_game_state(db, game)
    state = drawings.build_drawing_state(db, game, context.player)
    if changed:
        realtime.queue_game_state(background_tasks, context.room.join_code)
    return state


@router.put("/{room_code}/drawing", response_model=DrawingMutationResponse)
def save_drawing(
    room_code: str,
    payload: DrawingSaveRequest,
    background_tasks: BackgroundTasks,
    context: RoomContext = Depends(get_room_context),
    db: Session = Depends(get_db),
) -> DrawingMutationResponse:
    game = _get_game_or_404(db, context)
    drawing, progress_changed = drawings.save_drawing(
        db, game, context.player, payload.data
    )
    state = drawings.build_drawing_mutation(game, drawing)
    if progress_changed:
        realtime.queue_game_state(background_tasks, context.room.join_code)
    return state


@router.post(
    "/{room_code}/drawing/submit",
    response_model=DrawingMutationResponse,
)
def submit_drawing(
    room_code: str,
    background_tasks: BackgroundTasks,
    context: RoomContext = Depends(get_room_context),
    db: Session = Depends(get_db),
) -> DrawingMutationResponse:
    game = _get_game_or_404(db, context)
    drawing = drawings.submit_drawing(db, game, context.player)
    realtime.queue_game_state(background_tasks, context.room.join_code)
    return drawings.build_drawing_mutation(game, drawing)


@router.post(
    "/{room_code}/drawing/unsubmit",
    response_model=DrawingMutationResponse,
)
def unsubmit_drawing(
    room_code: str,
    background_tasks: BackgroundTasks,
    context: RoomContext = Depends(get_room_context),
    db: Session = Depends(get_db),
) -> DrawingMutationResponse:
    game = _get_game_or_404(db, context)
    drawing = drawings.unsubmit_drawing(db, game, context.player)
    realtime.queue_game_state(background_tasks, context.room.join_code)
    return drawings.build_drawing_mutation(game, drawing)
