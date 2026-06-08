"""Tier S — search/cached-index navigation.

Instead of driving a browser at the target origin (which trips anti-bot walls),
this tier queries a search provider's pre-crawled index and reads the cached
snippet or extracted page text. The origin is never contacted, so there is no
bot detection to defeat. This is the read-only "web search won" path.
"""

import logging
import time
from typing import Protocol

import httpx

from webcontrol.config import Settings
from webcontrol.core.errors import SearchError, SearchNotConfiguredError
from webcontrol.models.search import SearchResultItem

logger = logging.getLogger("webcontrol.search")

EXA_SEARCH_URL = "https://api.exa.ai/search"
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"


class SearchProvider(Protocol):
    name: str

    async def search(
        self,
        client: httpx.AsyncClient,
        query: str,
        *,
        max_results: int,
        fetch_contents: bool,
    ) -> list[SearchResultItem]: ...


class ExaProvider:
    """Exa neural search — returns full cleaned page text from its index."""

    name = "exa"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def search(
        self,
        client: httpx.AsyncClient,
        query: str,
        *,
        max_results: int,
        fetch_contents: bool,
    ) -> list[SearchResultItem]:
        payload: dict = {"query": query, "numResults": max_results}
        if fetch_contents:
            payload["contents"] = {"text": True, "highlights": True}
        resp = await client.post(
            EXA_SEARCH_URL,
            headers={"x-api-key": self._api_key, "Content-Type": "application/json"},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        items: list[SearchResultItem] = []
        for r in data.get("results", []):
            highlights = r.get("highlights") or []
            items.append(
                SearchResultItem(
                    title=r.get("title") or "",
                    url=r.get("url") or "",
                    snippet=highlights[0] if highlights else "",
                    content=r.get("text") or "",
                    published_date=r.get("publishedDate") or "",
                    score=r.get("score"),
                )
            )
        return items


class BraveProvider:
    """Brave Search — returns snippets/descriptions from its web index."""

    name = "brave"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def search(
        self,
        client: httpx.AsyncClient,
        query: str,
        *,
        max_results: int,
        fetch_contents: bool,
    ) -> list[SearchResultItem]:
        resp = await client.get(
            BRAVE_SEARCH_URL,
            headers={"X-Subscription-Token": self._api_key, "Accept": "application/json"},
            params={"q": query, "count": max_results},
        )
        resp.raise_for_status()
        data = resp.json()
        results = (data.get("web") or {}).get("results", [])
        return [
            SearchResultItem(
                title=r.get("title") or "",
                url=r.get("url") or "",
                snippet=r.get("description") or "",
            )
            for r in results[:max_results]
        ]


def build_provider(settings: Settings) -> SearchProvider:
    if not settings.search_api_key:
        raise SearchNotConfiguredError()
    if settings.search_provider == "exa":
        return ExaProvider(settings.search_api_key)
    if settings.search_provider == "brave":
        return BraveProvider(settings.search_api_key)
    raise SearchError(f"Unknown search provider: {settings.search_provider}")


class SearchTier:
    def __init__(
        self,
        settings: Settings,
        provider: SearchProvider | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._provider = provider or build_provider(settings)
        self._client = client or httpx.AsyncClient(timeout=settings.search_timeout_ms / 1000)

    @property
    def provider_name(self) -> str:
        return self._provider.name

    async def search(
        self,
        query: str,
        *,
        max_results: int | None = None,
        fetch_contents: bool | None = None,
    ) -> list[SearchResultItem]:
        if not query or not query.strip():
            raise SearchError("Search query must not be empty")
        n = max_results or self._settings.search_max_results
        fetch = self._settings.search_fetch_contents if fetch_contents is None else fetch_contents

        start = time.perf_counter()
        try:
            items = await self._provider.search(
                self._client, query, max_results=n, fetch_contents=fetch
            )
        except httpx.HTTPStatusError as exc:
            # Status only — never surface the API key or request headers.
            raise SearchError(
                f"Search provider '{self._provider.name}' returned HTTP {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            raise SearchError(
                f"Search provider '{self._provider.name}' request failed: {type(exc).__name__}"
            ) from exc

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "search via %s -> %d results",
            self._provider.name,
            len(items),
            extra={
                "provider": self._provider.name,
                "result_count": len(items),
                "duration_ms": round(duration_ms, 1),
            },
        )
        return items

    async def aclose(self) -> None:
        await self._client.aclose()
