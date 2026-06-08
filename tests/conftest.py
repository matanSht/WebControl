import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from webcontrol.api.app import create_app
from webcontrol.config import Settings
from webcontrol.core.service import WebControlService


@pytest_asyncio.fixture
async def settings():
    return Settings(headless=True, max_sessions=3, default_session_ttl_seconds=60)


@pytest_asyncio.fixture
async def app(settings):
    application = create_app(settings)
    service = WebControlService(settings)
    await service.startup()
    application.state.service = service
    yield application
    await service.shutdown()


@pytest_asyncio.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
