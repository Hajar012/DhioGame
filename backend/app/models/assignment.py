from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.game import Game
    from app.models.player import Player
    from app.models.reference_image import ReferenceImage


class Assignment(TimestampMixin, Base):
    __tablename__ = "assignments"
    __table_args__ = (
        UniqueConstraint("game_id", "player_id", name="uq_assignments_game_player"),
        UniqueConstraint(
            "game_id", "reference_image_id", name="uq_assignments_game_image"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    game_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), index=True, nullable=False
    )
    player_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"), index=True, nullable=False
    )
    reference_image_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reference_images.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    game: Mapped[Game] = relationship("Game", back_populates="assignments")
    player: Mapped[Player] = relationship("Player", back_populates="assignments")
    reference_image: Mapped[ReferenceImage] = relationship(
        "ReferenceImage", back_populates="assignment"
    )
