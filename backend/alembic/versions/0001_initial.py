"""Initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rooms",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("join_code", sa.String(length=12), nullable=False),
        sa.Column("host_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="waiting",
            nullable=False,
        ),
        sa.Column(
            "settings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_rooms"),
    )
    op.create_index("ix_rooms_join_code", "rooms", ["join_code"], unique=True)

    op.create_table(
        "players",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("room_id", sa.Uuid(), nullable=False),
        sa.Column("nickname", sa.String(length=50), nullable=False),
        sa.Column(
            "role",
            sa.String(length=20),
            server_default="player",
            nullable=False,
        ),
        sa.Column(
            "connection_status",
            sa.String(length=20),
            server_default="offline",
            nullable=False,
        ),
        sa.Column("session_token_hash", sa.String(length=128), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["room_id"],
            ["rooms.id"],
            name="fk_players_room_id_rooms",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_players"),
        sa.UniqueConstraint(
            "room_id", "nickname", name="uq_players_room_nickname"
        ),
    )
    op.create_index("ix_players_room_id", "players", ["room_id"], unique=False)
    op.create_index(
        "ix_players_session_token_hash",
        "players",
        ["session_token_hash"],
        unique=True,
    )

    op.create_table(
        "games",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("room_id", sa.Uuid(), nullable=False),
        sa.Column("mode", sa.String(length=30), nullable=False),
        sa.Column(
            "current_phase",
            sa.String(length=30),
            server_default="waiting_room",
            nullable=False,
        ),
        sa.Column("viewing_duration_seconds", sa.Integer(), nullable=True),
        sa.Column("drawing_duration_seconds", sa.Integer(), nullable=True),
        sa.Column("phase_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["room_id"],
            ["rooms.id"],
            name="fk_games_room_id_rooms",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_games"),
    )
    op.create_index("ix_games_room_id", "games", ["room_id"], unique=False)

    op.create_table(
        "reference_images",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("game_id", sa.Uuid(), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("content_type", sa.String(length=100), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["game_id"],
            ["games.id"],
            name="fk_reference_images_game_id_games",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_reference_images"),
    )
    op.create_index(
        "ix_reference_images_game_id",
        "reference_images",
        ["game_id"],
        unique=False,
    )
    op.create_index(
        "ix_reference_images_storage_key",
        "reference_images",
        ["storage_key"],
        unique=True,
    )

    op.create_table(
        "assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("game_id", sa.Uuid(), nullable=False),
        sa.Column("player_id", sa.Uuid(), nullable=False),
        sa.Column("reference_image_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["game_id"],
            ["games.id"],
            name="fk_assignments_game_id_games",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["player_id"],
            ["players.id"],
            name="fk_assignments_player_id_players",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reference_image_id"],
            ["reference_images.id"],
            name="fk_assignments_reference_image_id_reference_images",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_assignments"),
        sa.UniqueConstraint(
            "game_id", "player_id", name="uq_assignments_game_player"
        ),
        sa.UniqueConstraint(
            "game_id",
            "reference_image_id",
            name="uq_assignments_game_image",
        ),
    )
    op.create_index(
        "ix_assignments_game_id", "assignments", ["game_id"], unique=False
    )
    op.create_index(
        "ix_assignments_player_id", "assignments", ["player_id"], unique=False
    )
    op.create_index(
        "ix_assignments_reference_image_id",
        "assignments",
        ["reference_image_id"],
        unique=False,
    )

    op.create_table(
        "drawings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("game_id", sa.Uuid(), nullable=False),
        sa.Column("player_id", sa.Uuid(), nullable=False),
        sa.Column("data", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="draft",
            nullable=False,
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["game_id"],
            ["games.id"],
            name="fk_drawings_game_id_games",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["player_id"],
            ["players.id"],
            name="fk_drawings_player_id_players",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_drawings"),
        sa.UniqueConstraint("game_id", "player_id", name="uq_drawings_game_player"),
    )
    op.create_index("ix_drawings_game_id", "drawings", ["game_id"], unique=False)
    op.create_index(
        "ix_drawings_player_id", "drawings", ["player_id"], unique=False
    )

    op.create_table(
        "reveals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("game_id", sa.Uuid(), nullable=False),
        sa.Column(
            "reveal_order",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "current_index",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["game_id"],
            ["games.id"],
            name="fk_reveals_game_id_games",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_reveals"),
    )
    op.create_index("ix_reveals_game_id", "reveals", ["game_id"], unique=True)

    op.create_foreign_key(
        "fk_rooms_host_id_players",
        "rooms",
        "players",
        ["host_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_rooms_host_id_players", "rooms", type_="foreignkey")
    op.drop_index("ix_reveals_game_id", table_name="reveals")
    op.drop_table("reveals")
    op.drop_index("ix_drawings_player_id", table_name="drawings")
    op.drop_index("ix_drawings_game_id", table_name="drawings")
    op.drop_table("drawings")
    op.drop_index(
        "ix_assignments_reference_image_id", table_name="assignments"
    )
    op.drop_index("ix_assignments_player_id", table_name="assignments")
    op.drop_index("ix_assignments_game_id", table_name="assignments")
    op.drop_table("assignments")
    op.drop_index(
        "ix_reference_images_storage_key", table_name="reference_images"
    )
    op.drop_index("ix_reference_images_game_id", table_name="reference_images")
    op.drop_table("reference_images")
    op.drop_index("ix_games_room_id", table_name="games")
    op.drop_table("games")
    op.drop_index("ix_players_session_token_hash", table_name="players")
    op.drop_index("ix_players_room_id", table_name="players")
    op.drop_table("players")
    op.drop_index("ix_rooms_join_code", table_name="rooms")
    op.drop_table("rooms")
