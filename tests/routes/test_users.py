import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio.session import AsyncSession
from starlette import status

pytestmark = [pytest.mark.anyio]


async def test_auth_register(
    not_auth_client: AsyncClient,
    session: AsyncSession,
) -> None:
    data = {
        "email": "user@example.com",
        "password": "string",
        "username": "string",
        "role": "string",
    }
    response = await not_auth_client.post("/api/auth/register", json=data)
    assert response.status_code == status.HTTP_201_CREATED


async def test_users_me(client: AsyncClient, session: AsyncSession, user) -> None:
    response = await client.get("/api/users/me")
    assert response.status_code == status.HTTP_200_OK
