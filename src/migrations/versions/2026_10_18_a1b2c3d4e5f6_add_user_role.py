"""Compatibility revision for databases which recorded the earlier role migration."""

from typing import Sequence, Union

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "4f73b9006a12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing feature databases may already have this revision recorded.
    pass


def downgrade() -> None:
    pass
