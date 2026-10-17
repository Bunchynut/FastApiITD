from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from src.config import settings


@pytest.mark.asyncio
async def test_user_role_migration_preserves_users_and_enforces_enum():
    schema = f"migration_{uuid4().hex}"
    engine = create_async_engine(settings.DB_URL)
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            await connection.execute(text(f'SET search_path TO "{schema}"'))

            config = Config("alembic.ini")
            revision = ScriptDirectory.from_config(config).get_revision(
                "4f73b9006a12"
            )
            assert revision is not None, "user role migration is missing"

            def migrate(sync_connection, operation, revision):
                config.attributes["connection"] = sync_connection
                getattr(command, operation)(config, revision)

            await connection.run_sync(migrate, "upgrade", "bde324b4b6de")
            await connection.execute(
                text(
                    "INSERT INTO users (id, email, hashed_password, number, "
                    "first_name, second_name, sex) VALUES "
                    "(1, 'kept@example.com', 'hash', '+70000000000', 'Kept', "
                    "'User', 'male')"
                )
            )

            await connection.run_sync(migrate, "upgrade", "head")

            result = (
                await connection.execute(
                    text("SELECT role FROM users WHERE id = 1")
                )
            ).scalar_one()
            assert result == "user"
            labels = (
                await connection.execute(
                    text(
                        "SELECT enumlabel FROM pg_enum e JOIN pg_type t "
                        "ON t.oid = e.enumtypid JOIN pg_namespace n "
                        "ON n.oid = t.typnamespace WHERE t.typname = 'user_role' "
                        "AND n.nspname = :schema "
                        "ORDER BY e.enumsortorder"
                    ),
                    {"schema": schema},
                )
            ).scalars().all()
            assert labels == ["user", "admin"]
            column = (
                await connection.execute(
                    text(
                        "SELECT is_nullable, column_default FROM "
                        "information_schema.columns WHERE table_schema = :schema "
                        "AND table_name = 'users' AND column_name = 'role'"
                    ),
                    {"schema": schema},
                )
            ).one()
            assert column.is_nullable == "NO"
            assert "'user'" in column.column_default
            with pytest.raises(DBAPIError):
                async with connection.begin_nested():
                    await connection.execute(
                        text("UPDATE users SET role = 'owner' WHERE id = 1")
                    )

            await connection.run_sync(migrate, "downgrade", "bde324b4b6de")
            assert (
                await connection.execute(
                    text(
                        "SELECT email, hashed_password, number, first_name, "
                        "second_name, sex FROM users WHERE id = 1"
                    )
                )
            ).one() == (
                "kept@example.com",
                "hash",
                "+70000000000",
                "Kept",
                "User",
                "male",
            )
            assert (
                await connection.execute(
                    text(
                        "SELECT count(*) FROM information_schema.columns "
                        "WHERE table_schema = :schema AND table_name = 'users' "
                        "AND column_name = 'role'"
                    ),
                    {"schema": schema},
                )
            ).scalar_one() == 0
            assert (
                await connection.execute(
                    text(
                        "SELECT count(*) FROM pg_type t JOIN pg_namespace n "
                        "ON n.oid = t.typnamespace WHERE n.nspname = :schema "
                        "AND t.typname = 'user_role'"
                    ),
                    {"schema": schema},
                )
            ).scalar_one() == 0
    finally:
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
                )
        finally:
            await engine.dispose()
