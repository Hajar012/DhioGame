from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import DrawingStatus, GamePhase
from app.schemas.game import DrawingData


class RevealPlayer(BaseModel):
    player_id: UUID
    nickname: str
    drawing_status: DrawingStatus
    drawing_data: DrawingData | None


class RevealState(BaseModel):
    id: UUID
    game_id: UUID
    phase: GamePhase
    current_index: int
    total_players: int
    current_player: RevealPlayer | None
    original_revealed: bool
    server_time: datetime
