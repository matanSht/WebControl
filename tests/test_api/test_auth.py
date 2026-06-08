import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from webcontrol.api.app import create_app
from webcontrol.config import Settings
from webcontrol.core.service import WebControlService


@pytest_asyncio.fixture
async def auth_app():
    settings = Settings(headless=True, api_key="test-secret-key")
    application = create_app(settings)
    service = WebControlService(settings)
    await service.startup()
    application.state.service = service
    yield application
    await service.shutdown()


@pytest_asyncio.fixture
async def auth_client(auth_app):
    async with AsyncClient(
        transport=ASGITransport(app=auth_app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_no_auth_required(auth_client):
    resp = await auth_client.get("/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_missing_api_key_rejected(auth_client):
    resp = await auth_client.get("/api/v1/sessions")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_wrong_api_key_rejected(auth_client):
    resp = await auth_client.get(
        "/api/v1/sessions",
        headers={"x-api-key": "wrong-key"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_correct_api_key_accepted(auth_client):
    resp = await auth_client.get(
        "/api/v1/sessions",
        headers={"x-api-key": "test-secret-key"},
    )
    assert resp.status_code == 200
