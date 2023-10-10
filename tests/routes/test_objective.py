import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio.session import AsyncSession
from starlette import status

pytestmark = [pytest.mark.anyio]


async def test_health(client: AsyncClient, app: FastAPI) -> None:
    url = app.url_path_for("health_check")
    response = await client.get(url)
    assert response.status_code == status.HTTP_200_OK


async def test_(session: AsyncSession) -> None:
    ...
