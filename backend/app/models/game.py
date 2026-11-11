from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import GameMode, GamePhase

if TYPE_CHECKING:
    from app.models.assignment import Assignment
    from app.models.drawing import Drawing
    from app.models.reference_image import ReferenceImage
    from app.models.reveal import Reveal
    from app.models.room import Room


class Game(TimestampMixin, Base):
    __tablename__ = "games"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    room_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), index=True, nullable=False
    )
    mode: Mapped[GameMode] = mapped_column(
        Enum(
            GameMode,
            native_enum=False,
            length=30,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    current_phase: Mapped[GamePhase] = mapped_column(
        Enum(
            GamePhase,
            native_enum=False,
            length=30,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=GamePhase.WAITING_ROOM,
        server_default=GamePhase.WAITING_ROOM.value,
        nullable=False,
    )
    viewing_duration_seconds: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    drawing_duration_seconds: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    phase_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    phase_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    room: Mapped[Room] = relationship("Room", back_populates="games")
    reference_images: Mapped[list[ReferenceImage]] = relationship(
        "ReferenceImage",
        back_populates="game",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    assignments: Mapped[list[Assignment]] = relationship(
        "Assignment",
        back_populates="game",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    drawings: Mapped[list[Drawing]] = relationship(
        "Drawing",
        back_populates="game",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    reveal: Mapped[Reveal | None] = relationship(
        "Reveal",
        back_populates="game",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
