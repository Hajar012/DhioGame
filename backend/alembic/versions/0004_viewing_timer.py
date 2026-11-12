"""Track when each player has loaded the reference image

Revision ID: 0004_viewing_timer
Revises: 0003_game_flow
Create Date: 2026-11-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0004_viewing_timer"
down_revision: Union[str, None] = "0003_game_flow"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "drawings",
        sa.Column(
            "reference_loaded_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("drawings", "reference_loaded_at")
