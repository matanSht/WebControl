import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from webcontrol.api.app import create_app
from webcontrol.config import Settings
from webcontrol.core.errors import SearchError
from webcontrol.core.search_tier import ExaProvider, SearchTier
from webcontrol.core.service import WebControlService
from webcontrol.models.search import SearchResultItem


class FakeProvider:
    name = "fake"

    def __init__(self, items: list[SearchResultItem]):
        self._items = items
        self.calls: list[tuple] = []

    async def search(self, client, query, *, max_results, fetch_contents):
        self.calls.append((query, max_results, fetch_contents))
        return self._items[:max_results]


@pytest_asyncio.fixture
async def search_client():
    """App with a Tier-S search service backed by a fake provider (no browser, no network)."""
    settings = Settings(search_tier_enabled=False)
    application = create_app(settings)
    service = WebControlService(settings)
    enabled = Settings(search_tier_enabled=True, search_provider="exa", search_api_key="dummy")
    provider = FakeProvider(
        [
            SearchResultItem(
                title="Example Product",
                url="https://example.com/p",
                snippet="A snippet",
                content="Full extracted page text",
                score=0.9,
            )
        ]
    )
    service._search_tier = SearchTier(enabled, provider=provider)
    application.state.service = service
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as ac:
        yield ac, provider
    await service._search_tier.aclose()


# --- Endpoint behavior ---------------------------------------------------------


async def test_search_returns_results(search_client):
    client, _provider = search_client
    resp = await client.post("/api/v1/search", json={"query": "best widget"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["provider"] == "fake"
    assert body["tier_used"] == "search"
    assert body["results"][0]["url"] == "https://example.com/p"
    assert body["results"][0]["content"] == "Full extracted page text"


async def test_search_passes_through_overrides(search_client):
    client, provider = search_client
    resp = await client.post(
        "/api/v1/search",
        json={"query": "q", "max_results": 1, "fetch_contents": False},
    )

    assert resp.status_code == 200
    assert provider.calls == [("q", 1, False)]


async def test_search_not_configured_returns_503():
    settings = Settings(search_tier_enabled=False)
    application = create_app(settings)
    service = WebControlService(settings)  # no search tier
    application.state.service = service
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://test") as ac:
        resp = await ac.post("/api/v1/search", json={"query": "hi"})

    assert resp.status_code == 503


# --- Provider / tier units (no live network via httpx.MockTransport) -----------


async def test_exa_provider_parses_results():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "key"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "T",
                        "url": "https://x.com",
                        "text": "body text",
                        "highlights": ["snip"],
                        "score": 0.5,
                        "publishedDate": "2024-01-01",
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as c:
        items = await ExaProvider("key").search(c, "q", max_results=5, fetch_contents=True)

    assert items[0].url == "https://x.com"
    assert items[0].content == "body text"
    assert items[0].snippet == "snip"


async def test_search_tier_wraps_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={})

    settings = Settings(search_tier_enabled=True, search_api_key="k")
    tier = SearchTier(
        settings,
        provider=ExaProvider("k"),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    try:
        with pytest.raises(SearchError) as exc:
            await tier.search("q")
        assert "429" in str(exc.value)
    finally:
        await tier.aclose()


async def test_search_tier_rejects_empty_query():
    settings = Settings(search_tier_enabled=True, search_api_key="k")
    tier = SearchTier(settings, provider=FakeProvider([]))
    try:
        with pytest.raises(SearchError):
            await tier.search("   ")
    finally:
        await tier.aclose()
