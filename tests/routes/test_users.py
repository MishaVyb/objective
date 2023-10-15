import pytest
from httpx import AsyncClient
from starlette import status
from tests.conftest import ClientsFixture

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.usefixtures("session"),
]


async def test_auth_register(clients: ClientsFixture) -> None:
    data = {
        "email": "user@example.com",
        "password": "string",
        "username": "string",
        "role": "string",
    }
    response = await clients.no_auth.post("/api/auth/register", json=data)
    assert response.status_code == status.HTTP_201_CREATED


async def test_users_me(client: AsyncClient) -> None:
    response = await client.get("/api/users/me")
    assert response.status_code == status.HTTP_200_OK
