from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import RoomContext, get_room_context
from app.core.errors import AppError
from app.db.session import get_db
from app.models import Game
from app.schemas.reveal import RevealState
from app.services import games, images, realtime, reveals, rooms

router = APIRouter(prefix="/rooms", tags=["reveal"])


def _get_game_or_404(db: Session, context: RoomContext) -> Game:
    game = games.get_current_game(db, context.room)
    if game is None:
        raise AppError(404, "The game has not started")
    return game


@router.post("/{room_code}/reveal/start", response_model=RevealState)
def start_reveal(
    room_code: str,
    background_tasks: BackgroundTasks,
    context: RoomContext = Depends(get_room_context),
    db: Session = Depends(get_db),
) -> RevealState:
    rooms.require_host(context.room, context.player)
    game = _get_game_or_404(db, context)
    games.sync_game_state(db, game)
    reveal = reveals.start_reveal(db, context.room, game)
    state = reveals.build_reveal_state(db, game, reveal)
    realtime.queue_game_state(background_tasks, context.room.join_code)
    realtime.queue_reveal_state(background_tasks, context.room.join_code)
    return state


@router.get("/{room_code}/reveal", response_model=RevealState)
def read_reveal(
    room_code: str,
    context: RoomContext = Depends(get_room_context),
    db: Session = Depends(get_db),
) -> RevealState:
    game = _get_game_or_404(db, context)
    reveal = reveals.get_reveal_or_404(db, game)
    return reveals.build_reveal_state(db, game, reveal)


@router.post("/{room_code}/reveal/original", response_model=RevealState)
def reveal_original(
    room_code: str,
    background_tasks: BackgroundTasks,
    context: RoomContext = Depends(get_room_context),
    db: Session = Depends(get_db),
) -> RevealState:
    rooms.require_host(context.room, context.player)
    game = _get_game_or_404(db, context)
    reveal = reveals.reveal_original(db, game)
    state = reveals.build_reveal_state(db, game, reveal)
    realtime.queue_game_state(background_tasks, context.room.join_code)
    realtime.queue_reveal_state(background_tasks, context.room.join_code)
    return state


@router.post("/{room_code}/reveal/next", response_model=RevealState)
def next_reveal(
    room_code: str,
    background_tasks: BackgroundTasks,
    context: RoomContext = Depends(get_room_context),
    db: Session = Depends(get_db),
) -> RevealState:
    rooms.require_host(context.room, context.player)
    game = _get_game_or_404(db, context)
    reveal = reveals.next_reveal(db, context.room, game)
    state = reveals.build_reveal_state(db, game, reveal)
    realtime.queue_game_state(background_tasks, context.room.join_code)
    realtime.queue_reveal_state(background_tasks, context.room.join_code)
    realtime.queue_room_state(background_tasks, context.room.join_code)
    return state


@router.get(
    "/{room_code}/reveal/reference",
    response_class=FileResponse,
)
def read_reveal_reference(
    room_code: str,
    context: RoomContext = Depends(get_room_context),
    db: Session = Depends(get_db),
) -> FileResponse:
    game = _get_game_or_404(db, context)
    reveal = reveals.get_reveal_or_404(db, game)
    image = reveals.get_current_reference_image(
        db, context.room, game, reveal
    )
    path = images.get_storage_path(image.storage_key)
    if not path.is_file():
        raise AppError(404, "Original image file is missing")

    return FileResponse(
        path,
        media_type=image.content_type or "application/octet-stream",
        filename=image.original_filename or path.name,
    )
