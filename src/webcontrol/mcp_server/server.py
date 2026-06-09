from mcp.server.fastmcp import FastMCP

from webcontrol.core.service import WebControlService
from webcontrol.models.actions import (
    ClickRequest,
    ExecuteJsRequest,
    ExtractField,
    ExtractRequest,
    FillRequest,
    NavigateRequest,
    NetworkCaptureRequest,
    SelectRequest,
    SubmitRequest,
)
from webcontrol.models.search import SearchRequest
from webcontrol.models.session import SessionCreate


def create_mcp_server(get_service: callable) -> FastMCP:
    mcp = FastMCP("WebControl")

    @mcp.tool()
    async def create_session(
        name: str | None = None,
        ttl_seconds: int | None = None,
        viewport_width: int | None = None,
        viewport_height: int | None = None,
        user_agent: str | None = None,
        enable_tracing: bool = False,
    ) -> dict:
        """Create a new browser session with isolated cookies and storage. Set enable_tracing=true to record a Playwright trace for debugging."""
        service: WebControlService = get_service()
        result = await service.create_session(
            SessionCreate(
                name=name,
                ttl_seconds=ttl_seconds,
                viewport_width=viewport_width,
                viewport_height=viewport_height,
                user_agent=user_agent,
                enable_tracing=enable_tracing,
            )
        )
        return result.model_dump(mode="json")

    @mcp.tool()
    async def list_sessions() -> list[dict]:
        """List all active browser sessions."""
        service: WebControlService = get_service()
        return [s.model_dump(mode="json") for s in service.list_sessions()]

    @mcp.tool()
    async def close_session(session_id: str) -> dict:
        """Close a browser session and release its resources."""
        service: WebControlService = get_service()
        await service.close_session(session_id)
        return {"status": "closed", "session_id": session_id}

    @mcp.tool()
    async def navigate(
        session_id: str,
        url: str,
        wait_until: str = "domcontentloaded",
        fallback_to_search: bool = False,
        wait_for_selector: str | None = None,
        scroll_to_load: bool | None = None,
    ) -> dict:
        """Navigate to a URL and return the page content with interactive element refs.

        If the site serves an anti-bot block page, WebControl auto-escalates
        through its robustness tiers. The response includes `blocked`,
        `tier_used`, and `block_reason`, so a returned page is never mistaken for
        real content. If every browser tier is still blocked: by default this
        raises a Blocked error recommending the `search` tool; set
        `fallback_to_search=true` to instead return read-only search-index
        results in `search_fallback` (cannot click/interact).

        For pages whose content (prices, listings, ratings) is rendered by
        JavaScript after load, use `wait_for_selector` to block until a CSS
        selector for that content appears (e.g. ".a-price"), and/or
        `scroll_to_load=true` to auto-scroll and trigger lazy / on-scroll
        loaders before the page is read. Both make async content land before
        the snapshot.
        """
        service: WebControlService = get_service()
        result = await service.navigate(
            session_id,
            NavigateRequest(
                url=url,
                wait_until=wait_until,
                fallback_to_search=fallback_to_search,
                wait_for_selector=wait_for_selector,
                scroll_to_load=scroll_to_load,
            ),
        )
        return result.model_dump(mode="json")

    @mcp.tool()
    async def get_page_content(session_id: str) -> dict:
        """Get the current page content with interactive element refs without performing any action."""
        service: WebControlService = get_service()
        content = await service.get_page_content(session_id)
        return content.model_dump(mode="json")

    @mcp.tool()
    async def click(
        session_id: str,
        ref: str,
        button: str = "left",
        click_count: int = 1,
    ) -> dict:
        """Click an element by its ref ID (from get_page_content). Returns updated page content."""
        service: WebControlService = get_service()
        result = await service.click(
            session_id, ClickRequest(ref=ref, button=button, click_count=click_count)
        )
        return result.model_dump(mode="json")

    @mcp.tool()
    async def fill(session_id: str, ref: str, value: str) -> dict:
        """Fill a form field by its ref ID with the given value. Returns updated page content."""
        service: WebControlService = get_service()
        result = await service.fill(session_id, FillRequest(ref=ref, value=value))
        return result.model_dump(mode="json")

    @mcp.tool()
    async def select(session_id: str, ref: str, value: str) -> dict:
        """Select a dropdown option by its ref ID. Value can be option text or value. Returns updated page content."""
        service: WebControlService = get_service()
        result = await service.select(session_id, SelectRequest(ref=ref, value=value))
        return result.model_dump(mode="json")

    @mcp.tool()
    async def submit(session_id: str, ref: str) -> dict:
        """Submit a form by its ref ID (form element or submit button). Returns updated page content."""
        service: WebControlService = get_service()
        result = await service.submit(session_id, SubmitRequest(ref=ref))
        return result.model_dump(mode="json")

    @mcp.tool()
    async def extract(
        session_id: str,
        selector: str,
        fields: list[dict],
        limit: int = 50,
    ) -> dict:
        """Extract structured rows from the page via CSS selectors.

        The reliable way to pull repeated data (prices, titles, ratings) that the
        page snapshot truncates or misses — it reads exactly the fields you ask
        for from every matching row, bypassing the text-dump truncation.

        `selector` matches each row (e.g. ".s-result-item"). `fields` is a list of
        objects, each with:
          - name: output key for the value
          - selector (optional): CSS relative to the row; omit to use the row itself
          - attribute (optional): attribute to read (e.g. "href", "content"); omit for text

        Example: selector=".s-result-item", fields=[
            {"name": "title", "selector": "h2"},
            {"name": "price", "selector": ".a-offscreen"},
            {"name": "url", "selector": "a", "attribute": "href"}
        ]
        Returns {selector, count, rows}.
        """
        service: WebControlService = get_service()
        result = await service.extract(
            session_id,
            ExtractRequest(
                selector=selector,
                fields=[ExtractField(**f) for f in fields],
                limit=limit,
            ),
        )
        return result.model_dump(mode="json")

    @mcp.tool()
    async def get_html(session_id: str) -> dict:
        """Get the full rendered HTML of the current page (truncated to a configured
        cap). Full-fidelity fallback for when the curated page content misses
        JS-rendered data. Returns {url, html, truncated}."""
        service: WebControlService = get_service()
        result = await service.get_html(session_id)
        return result.model_dump(mode="json")

    @mcp.tool()
    async def get_accessibility_tree(session_id: str) -> dict:
        """Get the page's ARIA snapshot (accessibility tree as YAML). An
        alternative full-fidelity view of the page's semantic structure (roles,
        names, hierarchy) when the curated content snapshot misses something.
        Returns {url, snapshot}."""
        service: WebControlService = get_service()
        result = await service.get_accessibility_tree(session_id)
        return result.model_dump(mode="json")

    @mcp.tool()
    async def configure_network_capture(
        session_id: str,
        enabled: bool = True,
        url_filter: str | None = None,
        json_only: bool = True,
    ) -> dict:
        """Start or stop capturing the page's XHR/fetch responses for a session.

        The deepest extraction lever: instead of scraping JS-rendered values from
        the DOM, record the raw API payloads the page fetches — the JSON behind
        prices/listings on SPAs and search pages. Enable this BEFORE navigating or
        interacting, then read the payloads with get_network_capture.

        `json_only=true` (default) keeps only JSON responses; set false to capture
        all. `url_filter` keeps only responses whose URL contains that substring
        (e.g. "/api/" or "price"). Returns the active {enabled, url_filter, json_only}.
        """
        service: WebControlService = get_service()
        result = await service.configure_network_capture(
            session_id,
            NetworkCaptureRequest(enabled=enabled, url_filter=url_filter, json_only=json_only),
        )
        return result.model_dump(mode="json")

    @mcp.tool()
    async def get_network_capture(
        session_id: str,
        limit: int = 50,
        url_filter: str | None = None,
    ) -> dict:
        """Get the XHR/fetch responses captured for a session (most recent last).

        Requires capture to have been enabled with configure_network_capture
        before the page loaded. Each entry has url, status, method, resource_type,
        content_type, and body (parsed JSON or capped text). `url_filter` further
        narrows the returned set. Returns {count, responses}.
        """
        service: WebControlService = get_service()
        result = await service.get_network_capture(
            session_id, limit=limit, url_filter=url_filter
        )
        return result.model_dump(mode="json")

    @mcp.tool()
    async def clear_network_capture(session_id: str) -> dict:
        """Clear the captured XHR/fetch responses for a session."""
        service: WebControlService = get_service()
        await service.clear_network_capture(session_id)
        return {"status": "cleared", "session_id": session_id}

    @mcp.tool()
    async def screenshot(session_id: str) -> dict:
        """Take a screenshot of the current page. Returns base64-encoded PNG."""
        service: WebControlService = get_service()
        result = await service.screenshot(session_id)
        return result.model_dump(mode="json")

    @mcp.tool()
    async def execute_js(session_id: str, script: str) -> dict:
        """Execute JavaScript on the current page. Returns updated page content."""
        service: WebControlService = get_service()
        result = await service.execute_js(session_id, ExecuteJsRequest(script=script))
        return result.model_dump(mode="json")

    @mcp.tool()
    async def search(
        query: str,
        max_results: int | None = None,
        fetch_contents: bool | None = None,
    ) -> dict:
        """Search the web via a pre-crawled search index (Tier S).

        Reads results from a search provider's cache WITHOUT contacting the target
        site directly, so it bypasses anti-bot walls (e.g. Amazon's "Continue
        Shopping" block) that defeat a headless browser. Use this for read-only
        info gathering — prices, article text, "what's on this page" — when
        navigate() gets blocked or interaction isn't needed. No session required.
        Returns titles, URLs, snippets, and (when available) full extracted text.
        """
        service: WebControlService = get_service()
        result = await service.search(
            SearchRequest(query=query, max_results=max_results, fetch_contents=fetch_contents)
        )
        return result.model_dump(mode="json")

    @mcp.tool()
    async def get_session_activity(session_id: str, limit: int = 50) -> list[dict]:
        """Get the action history for a session. Shows what actions were performed, their timing, and success/failure."""
        service: WebControlService = get_service()
        return await service.get_session_activity(session_id, limit)

    @mcp.tool()
    async def get_session_stats(session_id: str) -> dict:
        """Get performance statistics for a session: total actions, success/error counts, avg/min/max duration."""
        service: WebControlService = get_service()
        return service.get_session_stats(session_id)

    return mcp
