"""api hardening: token revocation, one answer and one explanation per recommendation

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-25 10:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users", sa.Column("tokens_valid_after", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index(
        "uq_attempts_recommendation",
        "attempts",
        ["recommendation_id"],
        unique=True,
        postgresql_where=sa.text("recommendation_id IS NOT NULL"),
    )
    op.create_index(
        "uq_explanations_recommendation", "explanations", ["recommendation_id"], unique=True
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("uq_explanations_recommendation", table_name="explanations")
    op.drop_index("uq_attempts_recommendation", table_name="attempts")
    op.drop_column("users", "tokens_valid_after")
