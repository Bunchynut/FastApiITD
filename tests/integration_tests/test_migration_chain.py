from contextlib import nullcontext
from io import StringIO
import re
from uuid import uuid4
from unittest.mock import patch

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from src.DataBase import Base


def run_alembic(sync_connection, action, revision):
    class BorrowedEngine:
        def connect(self):
            return nullcontext(sync_connection)

    with patch("sqlalchemy.engine_from_config", return_value=BorrowedEngine()):
        getattr(command, action)(Config("alembic.ini"), revision)


async def migration_schema(test_engine):
    connection = await test_engine.connect()
    transaction = None
    try:
        transaction = await connection.begin()
        schema = "pytest_migration_" + uuid4().hex
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        await connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        return connection, transaction, schema
    except BaseException:
        if transaction is not None:
            await transaction.rollback()
        await connection.close()
        raise


def assert_models_match(sync_connection):
    differences = compare_metadata(
        MigrationContext.configure(sync_connection, opts={"compare_type": True}),
        Base.metadata,
    )
    assert differences == [], f"migration/model drift: {differences}"


async def test_base_head_base_head_round_trip_matches_metadata(test_engine):
    connection, transaction, schema = await migration_schema(test_engine)
    try:
        await connection.run_sync(lambda sync: run_alembic(sync, "upgrade", "head"))
        await connection.run_sync(lambda sync: run_alembic(sync, "downgrade", "base"))
        tables = await connection.scalars(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname=:schema AND tablename <> 'alembic_version'"
            ),
            {"schema": schema},
        )
        assert list(tables) == []

        await connection.run_sync(lambda sync: run_alembic(sync, "upgrade", "head"))
        await connection.run_sync(assert_models_match)
    finally:
        await transaction.rollback()
        await connection.close()


async def test_database_room_checks_reject_negatives_and_allow_zero(test_engine):
    connection, transaction, _schema = await migration_schema(test_engine)
    try:
        await connection.run_sync(lambda sync: run_alembic(sync, "upgrade", "head"))
        checks = await connection.run_sync(
            lambda sync: inspect(sync).get_check_constraints("rooms")
        )
        assert {check["name"] for check in checks} >= {
            "ck_rooms_price_nonnegative",
            "ck_rooms_quantity_nonnegative",
        }
        await connection.execute(
            text("INSERT INTO hotels (title, location) VALUES ('Hotel', 'Here')")
        )
        await connection.execute(
            text("INSERT INTO rooms (hotel_id, title, description, price, quantity) "
                 "VALUES (1, 'Zero', NULL, 0, 0)")
        )

        for price, quantity in [(-1, 0), (0, -1)]:
            with pytest.raises(IntegrityError):
                async with connection.begin_nested():
                    await connection.execute(
                        text(
                            "INSERT INTO rooms "
                            "(hotel_id, title, description, price, quantity) "
                            "VALUES (1, 'Invalid', NULL, :price, :quantity)"
                        ),
                        {"price": price, "quantity": quantity},
                    )
        count = await connection.scalar(text("SELECT count(*) FROM rooms"))
        assert count == 1
    finally:
        await transaction.rollback()
        await connection.close()


async def test_upgrade_removes_historical_duplicate_room_facility_links(test_engine):
    connection, transaction, _schema = await migration_schema(test_engine)
    try:
        await connection.run_sync(
            lambda sync: run_alembic(sync, "upgrade", "c7d8e9f01234")
        )
        await connection.execute(
            text("INSERT INTO hotels (title, location) VALUES ('Hotel', 'Here')")
        )
        await connection.execute(
            text("INSERT INTO rooms (hotel_id, title, description, price, quantity) "
                 "VALUES (1, 'Room', NULL, 0, 0)")
        )
        await connection.execute(
            text("INSERT INTO facilities (title) VALUES ('Wi-Fi')")
        )
        await connection.execute(
            text("INSERT INTO rooms_facilities (room_id, facility_id) "
                 "VALUES (1, 1), (1, 1)")
        )

        await connection.run_sync(lambda sync: run_alembic(sync, "upgrade", "head"))

        count = await connection.scalar(
            text("SELECT count(*) FROM rooms_facilities WHERE room_id=1 AND facility_id=1")
        )
        assert count == 1
        constraints = await connection.run_sync(
            lambda sync: inspect(sync).get_unique_constraints("rooms_facilities")
        )
        assert any(
            constraint["column_names"] == ["room_id", "facility_id"]
            for constraint in constraints
        )
        with pytest.raises(IntegrityError):
            async with connection.begin_nested():
                await connection.execute(
                    text("INSERT INTO rooms_facilities (room_id, facility_id) VALUES (1, 1)")
                )
        await connection.run_sync(assert_models_match)
    finally:
        await transaction.rollback()
        await connection.close()


@pytest.mark.parametrize(("price", "quantity"), [(-7, 0), (0, -7)])
async def test_upgrade_refuses_existing_negative_room_data_without_mutation(
    test_engine, price, quantity
):
    connection, transaction, _schema = await migration_schema(test_engine)
    try:
        await connection.run_sync(
            lambda sync: run_alembic(
                sync, "upgrade", "a1b2c3d4e5f6"
            )
        )
        await connection.execute(
            text("INSERT INTO hotels (title, location) VALUES ('Hotel', 'Here')")
        )
        await connection.execute(
            text("INSERT INTO rooms (hotel_id, title, description, price, quantity) "
                 "VALUES (1, 'Bad legacy row', NULL, :price, :quantity)"),
            {"price": price, "quantity": quantity},
        )

        with pytest.raises(RuntimeError, match="negative price or quantity"):
            await connection.run_sync(
                lambda sync: run_alembic(sync, "upgrade", "head")
            )

        row = await connection.execute(
            text("SELECT price, quantity FROM rooms WHERE title = 'Bad legacy row'")
        )
        assert row.one() == (price, quantity)
    finally:
        await transaction.rollback()
        await connection.close()


def test_offline_upgrade_head_emits_check_sql_without_connecting():
    output = StringIO()
    config = Config("alembic.ini", output_buffer=output)

    command.upgrade(config, "head", sql=True)

    sql = output.getvalue()
    assert "ALTER TABLE rooms ADD CONSTRAINT ck_rooms_price_nonnegative" in sql
    assert "ALTER TABLE rooms ADD CONSTRAINT ck_rooms_quantity_nonnegative" in sql


@pytest.mark.parametrize(
    ("price", "quantity", "reject"),
    [(0, 0, False), (-1, 0, True), (0, -1, True)],
)
async def test_offline_check_sql_executes_and_rejects_existing_negative_data(
    test_engine, price, quantity, reject
):
    output = StringIO()
    config = Config("alembic.ini", output_buffer=output)
    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    statements = re.findall(
        r"ALTER TABLE rooms ADD CONSTRAINT ck_rooms_(?:price|quantity)_nonnegative .*?;",
        sql,
        flags=re.IGNORECASE,
    )
    assert len(statements) == 2

    connection, transaction, _schema = await migration_schema(test_engine)
    try:
        await connection.run_sync(lambda sync: run_alembic(sync, "upgrade", "a1b2c3d4e5f6"))
        await connection.execute(
            text("INSERT INTO hotels (title, location) VALUES ('Hotel', 'Here')")
        )
        await connection.execute(
            text("INSERT INTO rooms (hotel_id, title, description, price, quantity) "
                 "VALUES (1, 'Offline row', NULL, :price, :quantity)"),
            {"price": price, "quantity": quantity},
        )
        if reject:
            with pytest.raises(IntegrityError):
                async with connection.begin_nested():
                    for statement in statements:
                        await connection.exec_driver_sql(statement[:-1])
        else:
            async with connection.begin_nested():
                for statement in statements:
                    await connection.exec_driver_sql(statement[:-1])
    finally:
        await transaction.rollback()
        await connection.close()
