"""Add lobby ready status and room-scoped reference images

Revision ID: 0002_lobby
Revises: 0001_initial
Create Date: 2026-11-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002_lobby"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "players",
        sa.Column(
            "is_ready",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )

    op.add_column(
        "reference_images",
        sa.Column("room_id", sa.Uuid(), nullable=True),
    )
    op.execute(
        """
        UPDATE reference_images AS ri
        SET room_id = g.room_id
        FROM games AS g
        WHERE ri.game_id = g.id AND ri.room_id IS NULL
        """
    )
    op.alter_column(
        "reference_images",
        "room_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
    op.alter_column(
        "reference_images",
        "game_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )
    op.create_foreign_key(
        "fk_reference_images_room_id_rooms",
        "reference_images",
        "rooms",
        ["room_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_reference_images_room_id",
        "reference_images",
        ["room_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_reference_images_room_id", table_name="reference_images")
    op.drop_constraint(
        "fk_reference_images_room_id_rooms",
        "reference_images",
        type_="foreignkey",
    )
    op.execute("DELETE FROM reference_images WHERE game_id IS NULL")
    op.alter_column(
        "reference_images",
        "game_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
    op.drop_column("reference_images", "room_id")
    op.drop_column("players", "is_ready")
