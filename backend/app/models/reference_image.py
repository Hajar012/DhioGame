from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.assignment import Assignment
    from app.models.game import Game


class ReferenceImage(TimestampMixin, Base):
    __tablename__ = "reference_images"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    game_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"), index=True, nullable=False
    )
    storage_key: Mapped[str] = mapped_column(
        String(512), unique=True, index=True, nullable=False
    )
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    game: Mapped[Game] = relationship("Game", back_populates="reference_images")
    assignment: Mapped[Assignment | None] = relationship(
        "Assignment",
        back_populates="reference_image",
        uselist=False,
    )
