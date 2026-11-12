from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models import Drawing, DrawingStatus, Game, GamePhase, Player
from app.schemas.game import (
    DrawingData,
    DrawingMutationResponse,
    DrawingState,
)
from app.services import games


def get_or_create_drawing(
    db: Session,
    game: Game,
    player: Player,
    *,
    for_update: bool = False,
) -> Drawing:
    statement = select(Drawing).where(
        Drawing.game_id == game.id,
        Drawing.player_id == player.id,
    )
    if for_update:
        statement = statement.with_for_update()
    statement = statement.execution_options(populate_existing=True)
    drawing = db.scalar(statement)
    if drawing is None:
        drawing = Drawing(
            game_id=game.id,
            player_id=player.id,
            status=DrawingStatus.DRAFT,
        )
        db.add(drawing)
        db.commit()
        db.refresh(drawing)
    return drawing


def parse_drawing_data(drawing: Drawing) -> DrawingData | None:
    if not drawing.data:
        return None
    try:
        return DrawingData.model_validate_json(drawing.data)
    except ValueError:
        return None


def _can_edit(game: Game, drawing: Drawing) -> bool:
    return (
        game.current_phase == GamePhase.DRAWING
        and drawing.status == DrawingStatus.DRAFT
    )


def build_drawing_state(
    db: Session, game: Game, player: Player
) -> DrawingState:
    drawing = get_or_create_drawing(db, game, player)
    return DrawingState(
        id=drawing.id,
        game_id=drawing.game_id,
        status=drawing.status,
        data=parse_drawing_data(drawing),
        submitted_at=drawing.submitted_at,
        updated_at=drawing.updated_at,
        can_edit=_can_edit(game, drawing),
        can_submit=_can_edit(game, drawing),
        can_unsubmit=(
            game.current_phase == GamePhase.DRAWING
            and drawing.status == DrawingStatus.SUBMITTED
        ),
        phase=game.current_phase,
        phase_ends_at=game.phase_ends_at,
        server_time=games.utcnow(),
    )


def build_drawing_mutation(
    game: Game, drawing: Drawing
) -> DrawingMutationResponse:
    return DrawingMutationResponse(
        id=drawing.id,
        game_id=drawing.game_id,
        status=drawing.status,
        submitted_at=drawing.submitted_at,
        updated_at=drawing.updated_at,
        can_edit=_can_edit(game, drawing),
        can_submit=_can_edit(game, drawing),
        can_unsubmit=(
            game.current_phase == GamePhase.DRAWING
            and drawing.status == DrawingStatus.SUBMITTED
        ),
        phase=game.current_phase,
        phase_ends_at=game.phase_ends_at,
        server_time=games.utcnow(),
    )


def save_drawing(
    db: Session,
    game: Game,
    player: Player,
    data: DrawingData,
) -> tuple[Drawing, bool]:
    drawing = get_or_create_drawing(db, game, player, for_update=True)

    if game.current_phase != GamePhase.DRAWING:
        raise AppError(409, "Drawing is not currently active")
    if drawing.status != DrawingStatus.DRAFT:
        raise AppError(
            409,
            "This drawing is submitted or locked. Reopen it before editing.",
        )

    serialized = data.model_dump_json()
    if len(serialized.encode("utf-8")) > get_settings().max_drawing_data_bytes:
        raise AppError(413, "Drawing data exceeds the allowed size")

    was_empty = drawing.data is None
    drawing.data = serialized
    db.commit()
    db.refresh(drawing)
    return drawing, was_empty


def submit_drawing(db: Session, game: Game, player: Player) -> Drawing:
    drawing = get_or_create_drawing(db, game, player, for_update=True)

    if game.current_phase != GamePhase.DRAWING:
        raise AppError(409, "Drawing is not currently active")
    if drawing.status == DrawingStatus.LOCKED:
        raise AppError(409, "This drawing is locked")
    if drawing.status == DrawingStatus.SUBMITTED:
        return drawing

    drawing.status = DrawingStatus.SUBMITTED
    drawing.submitted_at = games.utcnow()
    db.commit()
    db.refresh(drawing)
    return drawing


def unsubmit_drawing(db: Session, game: Game, player: Player) -> Drawing:
    drawing = get_or_create_drawing(db, game, player, for_update=True)

    if game.current_phase != GamePhase.DRAWING:
        raise AppError(409, "Drawing is not currently active")
    if drawing.status == DrawingStatus.LOCKED:
        raise AppError(409, "This drawing is locked")
    if drawing.status == DrawingStatus.DRAFT:
        return drawing

    drawing.status = DrawingStatus.DRAFT
    drawing.submitted_at = None
    db.commit()
    db.refresh(drawing)
    return drawing
