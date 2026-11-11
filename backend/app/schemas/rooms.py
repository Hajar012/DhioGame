from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.models.enums import ConnectionStatus, GameMode, PlayerRole, RoomStatus

Nickname = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=20),
]
JoinCode = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=4, max_length=12),
]

VIEWING_DURATIONS = {10, 20, 30, 60}
DRAWING_DURATIONS = {180, 300}


class RoomSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: GameMode = GameMode.SAME_IMAGE
    viewing_duration_seconds: int = 20
    drawing_duration_seconds: int | None = 180

    @field_validator("viewing_duration_seconds")
    @classmethod
    def validate_viewing_duration(cls, value: int) -> int:
        if value not in VIEWING_DURATIONS:
            raise ValueError(
                "viewing_duration_seconds must be one of 10, 20, 30, or 60"
            )
        return value

    @field_validator("drawing_duration_seconds")
    @classmethod
    def validate_drawing_duration(cls, value: int | None) -> int | None:
        if value is not None and value not in DRAWING_DURATIONS:
            raise ValueError(
                "drawing_duration_seconds must be 180, 300, or null (unlimited)"
            )
        return value


class RoomSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: GameMode | None = None
    viewing_duration_seconds: int | None = None
    drawing_duration_seconds: int | None = None

    @field_validator("viewing_duration_seconds")
    @classmethod
    def validate_viewing_duration(cls, value: int | None) -> int | None:
        if value is not None and value not in VIEWING_DURATIONS:
            raise ValueError(
                "viewing_duration_seconds must be one of 10, 20, 30, or 60"
            )
        return value

    @field_validator("drawing_duration_seconds")
    @classmethod
    def validate_drawing_duration(cls, value: int | None) -> int | None:
        if value is not None and value not in DRAWING_DURATIONS:
            raise ValueError(
                "drawing_duration_seconds must be 180, 300, or null (unlimited)"
            )
        return value

    @model_validator(mode="after")
    def validate_update(self) -> "RoomSettingsUpdate":
        fields = self.model_fields_set
        if not fields:
            raise ValueError("At least one setting must be provided")
        if "mode" in fields and self.mode is None:
            raise ValueError("mode cannot be null")
        if (
            "viewing_duration_seconds" in fields
            and self.viewing_duration_seconds is None
        ):
            raise ValueError("viewing_duration_seconds cannot be null")
        return self


class RoomCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nickname: Nickname
    settings: RoomSettings = Field(default_factory=RoomSettings)


class RoomJoin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    room_code: JoinCode
    nickname: Nickname

    @field_validator("room_code")
    @classmethod
    def normalize_room_code(cls, value: str) -> str:
        return value.upper()


class ReadyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_ready: bool


class PlayerResponse(BaseModel):
    id: UUID
    nickname: str
    role: PlayerRole
    is_ready: bool
    connection_status: ConnectionStatus
    is_host: bool


class RoomState(BaseModel):
    code: str
    status: RoomStatus
    settings: RoomSettings
    players: list[PlayerResponse]
    player_count: int
    min_players: int
    max_players: int
    ready_count: int
    uploaded_images: int
    required_images: int
    uploads_complete: bool
    can_start: bool
    created_at: datetime
    expires_at: datetime | None


class RoomSessionResponse(BaseModel):
    token: str
    player: PlayerResponse
    room: RoomState


class ReferenceImageResponse(BaseModel):
    id: UUID
    original_filename: str | None
    content_type: str | None
    file_size: int | None
    created_at: datetime
    content_url: str


class ImageUploadResponse(BaseModel):
    image: ReferenceImageResponse
    room: RoomState
