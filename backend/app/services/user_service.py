import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User

DEFAULT_USER_EMAIL = "vivan@jobsearchai.local"


async def get_or_create_default_user(db: AsyncSession) -> User:
    """Returns the primary user for single-user MVP, creating if non-existent."""
    stmt = select(User).limit(1)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            id=uuid.uuid4(),
            email=DEFAULT_USER_EMAIL,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return user
