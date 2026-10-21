"""Remove duplicate room facility links and enforce pair uniqueness."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d9e0f1234567"
down_revision: Union[str, Sequence[str], None] = "c7d8e9f01234"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM rooms_facilities older USING rooms_facilities newer "
            "WHERE older.room_id = newer.room_id "
            "AND older.facility_id = newer.facility_id AND older.ctid < newer.ctid"
        )
    )
    op.create_unique_constraint(
        "uq_rooms_facilities_room_facility",
        "rooms_facilities",
        ["room_id", "facility_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_rooms_facilities_room_facility", "rooms_facilities", type_="unique"
    )
