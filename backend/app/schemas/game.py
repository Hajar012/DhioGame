from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DrawingStatus, GameMode, GamePhase


class Point(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float
    y: float


class Stroke(BaseModel):
    model_config = ConfigDict(extra="forbid")

    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    size: float = Field(gt=0, le=200)
    erase: bool = False
    points: list[Point] = Field(min_length=1, max_length=20_000)


class DrawingData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 1
    width: int = Field(default=1600, ge=100, le=5000)
    height: int = Field(default=1000, ge=100, le=5000)
    strokes: list[Stroke] = Field(default_factory=list, max_length=10_000)


class DrawingSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: DrawingData


class GamePlayerProgress(BaseModel):
    player_id: UUID
    nickname: str
    is_connected: bool
    drawing_status: DrawingStatus
    has_drawing: bool


class GameState(BaseModel):
    id: UUID
    room_code: str
    mode: GameMode
    phase: GamePhase
    viewing_duration_seconds: int | None
    drawing_duration_seconds: int | None
    phase_started_at: datetime | None
    phase_ends_at: datetime | None
    started_at: datetime | None
    server_time: datetime
    player_count: int
    submitted_count: int
    drawings_locked: bool
    reference_available: bool
    players: list[GamePlayerProgress]


class DrawingState(BaseModel):
    id: UUID
    game_id: UUID
    status: DrawingStatus
    data: DrawingData | None
    submitted_at: datetime | None
    updated_at: datetime
    can_edit: bool
    can_submit: bool
    can_unsubmit: bool
    phase: GamePhase
    phase_ends_at: datetime | None
    server_time: datetime


class DrawingMutationResponse(BaseModel):
    id: UUID
    game_id: UUID
    status: DrawingStatus
    submitted_at: datetime | None
    updated_at: datetime
    can_edit: bool
    can_submit: bool
    can_unsubmit: bool
    phase: GamePhase
    phase_ends_at: datetime | None
    server_time: datetime
