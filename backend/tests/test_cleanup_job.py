"""
Tests for cleanup job that hard deletes expired user accounts
"""

from datetime import datetime, timedelta

import pytest
from arq.worker import Worker
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.worker.functions import cleanup_expired_deleted_users
from src.app.models.user import User
from src.app.schemas.user import UserRead


class MockWorkerContext:
    """Mock ARQ worker context for testing"""

    pass


@pytest.mark.asyncio
async def test_cleanup_expired_users(async_session: AsyncSession, test_user: User):
    """Test cleanup job deletes users deleted > 30 days ago"""
    # Set user as deleted 31 days ago
    test_user.is_deleted = True
    test_user.deleted_at = datetime.utcnow() - timedelta(days=31)
    await async_session.commit()
    user_id = test_user.id

    # Run cleanup job
    ctx = MockWorkerContext()
    result = await cleanup_expired_deleted_users(ctx)

    # Verify user was deleted
    assert "Deleted 1" in result or "deleted 1" in result.lower()

    # Verify user no longer exists in database
    stmt = select(User).where(User.id == user_id)
    result = await async_session.execute(stmt)
    deleted_user = result.scalar_one_or_none()
    assert deleted_user is None


@pytest.mark.asyncio
async def test_cleanup_keeps_recent_deleted_users(
    async_session: AsyncSession, test_user: User
):
    """Test cleanup job keeps users deleted < 30 days ago"""
    # Set user as deleted 29 days ago (within grace period)
    test_user.is_deleted = True
    test_user.deleted_at = datetime.utcnow() - timedelta(days=29)
    await async_session.commit()
    user_id = test_user.id

    # Run cleanup job
    ctx = MockWorkerContext()
    result = await cleanup_expired_deleted_users(ctx)

    # Verify no users were deleted
    assert "No users to cleanup" in result or "Deleted 0" in result

    # Verify user still exists
    stmt = select(User).where(User.id == user_id)
    result = await async_session.execute(stmt)
    existing_user = result.scalar_one_or_none()
    assert existing_user is not None
    assert existing_user.is_deleted is True


@pytest.mark.asyncio
async def test_cleanup_keeps_active_users(async_session: AsyncSession, test_user: User):
    """Test cleanup job keeps active (non-deleted) users"""
    # Ensure user is not deleted
    test_user.is_deleted = False
    test_user.deleted_at = None
    await async_session.commit()
    user_id = test_user.id

    # Run cleanup job
    ctx = MockWorkerContext()
    result = await cleanup_expired_deleted_users(ctx)

    # Verify user still exists
    stmt = select(User).where(User.id == user_id)
    result = await async_session.execute(stmt)
    existing_user = result.scalar_one_or_none()
    assert existing_user is not None
    assert existing_user.is_deleted is False


@pytest.mark.asyncio
async def test_cleanup_multiple_expired_users(
    async_session: AsyncSession, test_user: User, test_superuser: User
):
    """Test cleanup job deletes multiple expired users"""
    # Set both users as deleted > 30 days ago
    test_user.is_deleted = True
    test_user.deleted_at = datetime.utcnow() - timedelta(days=35)
    test_superuser.is_deleted = True
    test_superuser.deleted_at = datetime.utcnow() - timedelta(days=40)
    await async_session.commit()

    user_id = test_user.id
    superuser_id = test_superuser.id

    # Run cleanup job
    ctx = MockWorkerContext()
    result = await cleanup_expired_deleted_users(ctx)

    # Verify both users were deleted
    assert "Deleted 2" in result or "deleted 2" in result.lower()

    # Verify neither user exists
    stmt = select(User).where(User.id.in_([user_id, superuser_id]))
    result = await async_session.execute(stmt)
    remaining_users = result.scalars().all()
    assert len(remaining_users) == 0


@pytest.mark.asyncio
async def test_cleanup_mixed_users(
    async_session: AsyncSession, test_user: User, test_superuser: User
):
    """Test cleanup with mix of expired, recent, and active users"""
    # test_user: expired (deleted 35 days ago)
    test_user.is_deleted = True
    test_user.deleted_at = datetime.utcnow() - timedelta(days=35)

    # test_superuser: recent (deleted 10 days ago)
    test_superuser.is_deleted = True
    test_superuser.deleted_at = datetime.utcnow() - timedelta(days=10)

    await async_session.commit()

    expired_user_id = test_user.id
    recent_user_id = test_superuser.id

    # Run cleanup job
    ctx = MockWorkerContext()
    result = await cleanup_expired_deleted_users(ctx)

    # Verify only expired user was deleted
    assert "Deleted 1" in result or "deleted 1" in result.lower()

    # Verify expired user is gone
    stmt = select(User).where(User.id == expired_user_id)
    result = await async_session.execute(stmt)
    assert result.scalar_one_or_none() is None

    # Verify recent user still exists
    stmt = select(User).where(User.id == recent_user_id)
    result = await async_session.execute(stmt)
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_cleanup_exactly_30_days(async_session: AsyncSession, test_user: User):
    """Test cleanup behavior at exactly 30 days boundary"""
    # Set user as deleted exactly 30 days ago
    test_user.is_deleted = True
    test_user.deleted_at = datetime.utcnow() - timedelta(days=30, seconds=1)
    await async_session.commit()
    user_id = test_user.id

    # Run cleanup job
    ctx = MockWorkerContext()
    result = await cleanup_expired_deleted_users(ctx)

    # Should be deleted (> 30 days)
    assert "Deleted 1" in result or "deleted 1" in result.lower()

    # Verify user was deleted
    stmt = select(User).where(User.id == user_id)
    result = await async_session.execute(stmt)
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_cleanup_no_deleted_users(async_session: AsyncSession):
    """Test cleanup when there are no deleted users"""
    ctx = MockWorkerContext()
    result = await cleanup_expired_deleted_users(ctx)

    # Should return message indicating no cleanup needed
    assert "No users to cleanup" in result or "Deleted 0" in result


@pytest.mark.asyncio
async def test_cleanup_user_with_null_deleted_at(
    async_session: AsyncSession, test_user: User
):
    """Test cleanup ignores users with is_deleted=True but deleted_at=NULL"""
    # Set inconsistent state (should not happen in practice)
    test_user.is_deleted = True
    test_user.deleted_at = None
    await async_session.commit()
    user_id = test_user.id

    # Run cleanup job
    ctx = MockWorkerContext()
    result = await cleanup_expired_deleted_users(ctx)

    # User should NOT be deleted (deleted_at is NULL)
    assert "No users to cleanup" in result or "Deleted 0" in result

    # Verify user still exists
    stmt = select(User).where(User.id == user_id)
    result = await async_session.execute(stmt)
    assert result.scalar_one_or_none() is not None
