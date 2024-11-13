import pytest
from starlette import status

from app.client import ObjectiveClient
from tests.conftest import TEST_USERS

pytestmark = [
    pytest.mark.anyio,
]


async def test_auth_register(client: ObjectiveClient) -> None:
    data = {
        "email": "user@example.com",
        "password": "string",
        "username": "string",
        "role": "string",
    }
    response = await client._session.post("/api/v2/auth/register", json=data)
    assert response.status_code == status.HTTP_201_CREATED


async def test_users_me(client: ObjectiveClient) -> None:
    result = await client.get_user_me()
    assert result.username == TEST_USERS[1].username
