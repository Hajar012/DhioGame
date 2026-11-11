from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import RoomStatus

if TYPE_CHECKING:
    from app.models.game import Game
    from app.models.player import Player
    from app.models.reference_image import ReferenceImage


class Room(TimestampMixin, Base):
    __tablename__ = "rooms"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    join_code: Mapped[str] = mapped_column(
        String(12), unique=True, index=True, nullable=False
    )
    host_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "players.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_rooms_host_id_players",
        ),
        nullable=True,
    )
    status: Mapped[RoomStatus] = mapped_column(
        Enum(
            RoomStatus,
            native_enum=False,
            length=20,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=RoomStatus.WAITING,
        server_default=RoomStatus.WAITING.value,
        nullable=False,
    )
    settings: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    host: Mapped[Player | None] = relationship(
        "Player",
        foreign_keys=[host_id],
        post_update=True,
    )
    players: Mapped[list[Player]] = relationship(
        "Player",
        back_populates="room",
        foreign_keys="Player.room_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    games: Mapped[list[Game]] = relationship(
        "Game",
        back_populates="room",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    reference_images: Mapped[list[ReferenceImage]] = relationship(
        "ReferenceImage",
        back_populates="room",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
