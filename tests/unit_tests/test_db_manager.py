from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.booking import BookingRepository
from src.repositories.factilities import FacilitiesRepository, RoomsFacilitiesRepository
from src.repositories.hotels import HotelsRepositories
from src.repositories.rooms import RoomsRepositories
from src.repositories.users import UsersRepository
from src.utils.db_manager import DBManager


@pytest.fixture
def session():
    return AsyncMock(spec=AsyncSession)


async def test_manager_shares_one_session_between_repositories(session):
    factory = Mock(return_value=session)
    manager = DBManager(session_factory=factory)

    async with manager as db:
        assert db is manager
        for name, repository in (
            ("hotels", HotelsRepositories),
            ("rooms", RoomsRepositories),
            ("users", UsersRepository),
            ("booking", BookingRepository),
            ("facilities", FacilitiesRepository),
            ("rooms_facilities", RoomsFacilitiesRepository),
        ):
            assert isinstance(getattr(db, name), repository)
            assert getattr(db, name).session is session
        session.close.assert_not_awaited()

    factory.assert_called_once_with()
    session.close.assert_awaited_once_with()
    session.commit.assert_not_awaited()


async def test_commit_is_explicit_and_closes_session(session):
    async with DBManager(session_factory=lambda: session) as db:
        await db.commit()
        session.commit.assert_awaited_once_with()
        session.close.assert_not_awaited()
    session.close.assert_awaited_once_with()


async def test_manager_closes_session_when_body_raises(session):
    error = RuntimeError("operation failed")
    with pytest.raises(RuntimeError) as caught:
        async with DBManager(session_factory=lambda: session):
            raise error
    assert caught.value is error
    session.close.assert_awaited_once_with()
    session.commit.assert_not_awaited()


async def test_manager_preserves_commit_failure_and_closes_session(session):
    error = RuntimeError("commit failed")
    session.commit.side_effect = error

    with pytest.raises(RuntimeError) as caught:
        async with DBManager(session_factory=lambda: session) as db:
            await db.commit()
    assert caught.value is error
    session.close.assert_awaited_once_with()
