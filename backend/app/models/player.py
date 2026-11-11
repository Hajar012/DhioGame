from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    String,
    UniqueConstraint,
    Uuid,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import ConnectionStatus, PlayerRole

if TYPE_CHECKING:
    from app.models.assignment import Assignment
    from app.models.drawing import Drawing
    from app.models.room import Room


class Player(TimestampMixin, Base):
    __tablename__ = "players"
    __table_args__ = (
        UniqueConstraint("room_id", "nickname", name="uq_players_room_nickname"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    room_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), index=True, nullable=False
    )
    nickname: Mapped[str] = mapped_column(String(50), nullable=False)
    role: Mapped[PlayerRole] = mapped_column(
        Enum(
            PlayerRole,
            native_enum=False,
            length=20,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=PlayerRole.PLAYER,
        server_default=PlayerRole.PLAYER.value,
        nullable=False,
    )
    connection_status: Mapped[ConnectionStatus] = mapped_column(
        Enum(
            ConnectionStatus,
            native_enum=False,
            length=20,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        default=ConnectionStatus.OFFLINE,
        server_default=ConnectionStatus.OFFLINE.value,
        nullable=False,
    )
    session_token_hash: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    is_ready: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), nullable=False
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    room: Mapped[Room] = relationship(
        "Room",
        back_populates="players",
        foreign_keys=[room_id],
    )
    assignments: Mapped[list[Assignment]] = relationship(
        "Assignment",
        back_populates="player",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    drawings: Mapped[list[Drawing]] = relationship(
        "Drawing",
        back_populates="player",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
