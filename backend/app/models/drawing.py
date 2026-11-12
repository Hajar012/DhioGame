from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import DrawingStatus

if TYPE_CHECKING:
    from app.models.game import Game
    from app.models.player import Player


class Drawing(TimestampMixin, Base):
    __tablename__ = "drawings"
    __table_args__ = (
        UniqueConstraint("game_id", "player_id", name="uq_drawings_game_player"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    game_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), index=True, nullable=False
    )
    player_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"), index=True, nullable=False
    )
    data: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_loaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[DrawingStatus] = mapped_column(
        Enum(
            DrawingStatus,
            native_enum=False,
            length=20,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=DrawingStatus.DRAFT,
        server_default=DrawingStatus.DRAFT.value,
        nullable=False,
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    game: Mapped[Game] = relationship("Game", back_populates="drawings")
    player: Mapped[Player] = relationship("Player", back_populates="drawings")
