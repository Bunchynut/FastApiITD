"""Role migration compatibility for every released database starting point."""

from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text


def run_alembic(sync_connection, action, revision):
    config = Config("alembic.ini")
    config.attributes["connection"] = sync_connection
    getattr(command, action)(config, revision)


def test_role_revisions_form_one_chain_with_both_published_revisions():
    scripts = ScriptDirectory.from_config(Config("alembic.ini"))

    assert scripts.get_heads() == ["d9e0f1234567"]
    assert scripts.get_revision("a1b2c3d4e5f6") is not None
    assert scripts.get_revision("d9e0f1234567") is not None
    ancestors = {revision.revision for revision in scripts.iterate_revisions(
        "d9e0f1234567", "bde324b4b6de"
    )}
    assert {"4f73b9006a12", "a1b2c3d4e5f6", "c7d8e9f01234"} <= ancestors


@pytest.mark.parametrize("starting_state", ["base", "master_role", "feature_role"])
async def test_role_migration_upgrades_and_downgrades_each_released_state(
    test_engine, starting_state
):
    schema = f"pytest_role_migration_{uuid4().hex}"
    async with test_engine.connect() as connection:
        transaction = await connection.begin()
        try:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            await connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))

            if starting_state == "base":
                await connection.run_sync(
                    lambda sync: run_alembic(sync, "upgrade", "bde324b4b6de")
                )
            elif starting_state == "master_role":
                await connection.run_sync(
                    lambda sync: run_alembic(sync, "upgrade", "4f73b9006a12")
                )
            else:
                await connection.run_sync(
                    lambda sync: run_alembic(sync, "upgrade", "bde324b4b6de")
                )
                # The released a1 migration added the role to existing users.
                await connection.execute(
                    text(
                        "INSERT INTO users (email, hashed_password, number, first_name, "
                        "second_name, sex) VALUES ('kept@example.com', 'hash', "
                        "'+70000000000', 'Kept', 'User', 'male')"
                    )
                )
                await connection.execute(
                    text("CREATE TYPE user_role AS ENUM ('user', 'admin')")
                )
                await connection.execute(
                    text(
                        "ALTER TABLE users ADD COLUMN role user_role "
                        "NOT NULL DEFAULT 'user'"
                    )
                )
                await connection.run_sync(
                    lambda sync: run_alembic(sync, "stamp", "a1b2c3d4e5f6")
                )

            if starting_state != "feature_role":
                await connection.execute(
                    text(
                        "INSERT INTO users (email, hashed_password, number, first_name, "
                        "second_name, sex) VALUES ('kept@example.com', 'hash', "
                        "'+70000000000', 'Kept', 'User', 'male')"
                    )
                )
            await connection.run_sync(
                lambda sync: run_alembic(sync, "upgrade", "head")
            )

            assert (
                await connection.scalar(
                    text("SELECT role::text FROM users WHERE email='kept@example.com'")
                )
            ) == "user"
            labels = await connection.scalars(
                text(
                    "SELECT enumlabel FROM pg_enum e JOIN pg_type t "
                    "ON t.oid=e.enumtypid JOIN pg_namespace n ON n.oid=t.typnamespace "
                    "WHERE t.typname='user_role' AND n.nspname=:schema "
                    "ORDER BY e.enumsortorder"
                ),
                {"schema": schema},
            )
            assert list(labels) == ["user", "admin"]
            role_column = (
                await connection.execute(
                    text(
                        "SELECT is_nullable, column_default FROM information_schema.columns "
                        "WHERE table_schema=:schema AND table_name='users' "
                        "AND column_name='role'"
                    ),
                    {"schema": schema},
                )
            ).one()
            assert role_column.is_nullable == "NO"
            assert "'user'" in role_column.column_default

            await connection.run_sync(
                lambda sync: run_alembic(sync, "downgrade", "bde324b4b6de")
            )
            assert await connection.scalar(
                text(
                    "SELECT count(*) FROM information_schema.columns "
                    "WHERE table_schema=:schema AND table_name='users' "
                    "AND column_name='role'"
                ),
                {"schema": schema},
            ) == 0
            assert await connection.scalar(
                text(
                    "SELECT count(*) FROM pg_type t JOIN pg_namespace n "
                    "ON n.oid=t.typnamespace WHERE n.nspname=:schema "
                    "AND t.typname='user_role'"
                ),
                {"schema": schema},
            ) == 0
            assert await connection.scalar(
                text("SELECT email FROM users WHERE id=1")
            ) == "kept@example.com"
        finally:
            await transaction.rollback()
