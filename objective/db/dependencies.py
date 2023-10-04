from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from starlette.requests import Request


async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """
    Create and get database session.

    :param request: current request.
    :yield: database session.
    """
    engine: AsyncEngine = request.app.state.db_engine
    async with AsyncSession(engine, expire_on_commit=False) as session:
        async with session.begin():
            yield session
