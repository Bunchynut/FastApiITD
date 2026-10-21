"""Require nonnegative room prices and quantities."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c7d8e9f01234"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if not op.get_context().as_sql:
        invalid_count = op.get_bind().scalar(
            sa.text("SELECT count(*) FROM rooms WHERE price < 0 OR quantity < 0")
        )
        if invalid_count:
            raise RuntimeError(
                "Cannot add room constraints: found existing rooms with negative price or quantity. "
                "Correct those rows before retrying the migration."
            )

    op.create_check_constraint("ck_rooms_price_nonnegative", "rooms", "price >= 0")
    op.create_check_constraint(
        "ck_rooms_quantity_nonnegative", "rooms", "quantity >= 0"
    )


def downgrade() -> None:
    op.drop_constraint("ck_rooms_quantity_nonnegative", "rooms", type_="check")
    op.drop_constraint("ck_rooms_price_nonnegative", "rooms", type_="check")
