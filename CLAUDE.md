# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WebControl is a headless browser automation service for LLM agents. It navigates pages, reads structured content, and interacts with elements (click, fill, select, submit) — exposed via both a REST API and MCP (Model Context Protocol) server on a single port.

## Git Policy

Never run `git commit` or `git push` without explicit user approval. Show what will be committed or pushed and wait for confirmation before executing.

## Commands

```bash
# Setup (first time)
python3 -m venv .venv && source .venv/bin/activate
pip install ".[dev]"
playwright install chromium

# Activate venv (subsequent times)
source .venv/bin/activate

# Reinstall after code changes (required since editable installs are broken on Python 3.14)
pip install ".[dev]"

# Run server (REST at /api/v1, MCP at /mcp, health at /health)
webcontrol serve
webcontrol serve --port 9000

# Run MCP over stdio (for Claude Desktop / Cursor)
webcontrol mcp-stdio

# Docker
docker compose up --build

# Tests
pytest tests/ -v
pytest tests/test_api/test_routes.py -v
pytest tests/test_api/test_routes.py::test_navigate_and_get_content -v

# Lint and format
ruff check src/ tests/
ruff format src/ tests/
```

## Architecture

```
LLM Agent → REST (/api/v1) or MCP tools (/mcp)
              ↓
        ApiKeyMiddleware (optional, via WC_API_KEY)
              ↓
    WebControlService  ← facade, single entry point (core/service.py)
              ↓
    NavigationEscalator← navigate() tier ladder + block detection (core/navigation_escalation.py)
    SessionManager     ← BrowserSession per caller (core/session_manager.py)
    PageParser         ← DOM → PageContent with refs e1..eN (core/page_parser.py)
    ActionExecutor     ← ref → Locator, execute with retry (core/action_executor.py)
    SearchTier         ← Tier S: pre-crawled search index, no origin (core/search_tier.py)
              ↓
    BrowserManager     ← single Playwright Browser instance (core/browser_manager.py)
```

**Dual API, shared core.** REST routes (`api/routes_*.py`) and MCP tools (`mcp_server/server.py`) are thin wrappers over the same `WebControlService`. They share browser sessions and state in one process.

**Element ref system.** `PageParser` queries the DOM for visible interactive elements, assigns short refs (`e1`–`eN`), and stores a `dict[str, Locator]` in `BrowserSession.ref_map`. Every action response includes fresh `PageContent` with new refs. If a ref is stale, `ActionExecutor` raises `ElementNotFoundError`.

**Session isolation.** One Playwright `BrowserContext` per session (separate cookies, storage, cache). Per-session `asyncio.Lock` serializes actions within a session; different sessions run concurrently. Background cleanup evicts sessions past TTL.

**Retry.** `core/retry.py` wraps Playwright calls with configurable retries on transient errors.

**Navigation robustness.** Anti-bot walls (Amazon, Cloudflare) often serve a block page with HTTP 200, so `goto()` succeeds while returning junk. `navigate()` goes through `NavigationEscalator` (`core/navigation_escalation.py`), which runs `detect_block()` (`core/block_detection.py`) after each attempt and climbs a tier ladder: **direct** (stealth, `core/stealth.py`) → **behavioral** (jitter + networkidle + scroll/mouse) → **proxy** (rebuilds the context through `WC_PROXY_SERVER`; skipped if unset) → terminal. On terminal block it raises `BlockedError` (HTTP 409), or — when `NavigateRequest.fallback_to_search=true` — returns Tier S search results in `ActionResult.search_fallback`. Every `ActionResult` carries `blocked`, `tier_used`, `block_reason` so a block page is never reported as success. Full detail: [docs/robustness.md](docs/robustness.md).

## Adding a New Action

A new action (e.g., `hover`) touches four files in order:

1. **`models/actions.py`** — add `HoverRequest(BaseModel)` with the parameters
2. **`core/action_executor.py`** — add `async def hover(self, session, req)` that resolves the ref, calls Playwright, re-parses, and returns `ActionResult`
3. **`core/service.py`** — add `async def hover(self, session_id, req)` that acquires the session lock and delegates to the executor
4. **`api/routes_actions.py`** — add the REST endpoint; **`mcp_server/server.py`** — add the MCP tool. Both call `service.hover()`.

Follow the existing `click`/`fill` implementations as templates.

## Testing

Tests use `httpx.AsyncClient` with `ASGITransport` against the FastAPI app. The ASGI lifespan is **not** triggered by the test transport, so `conftest.py` manually creates a `WebControlService`, calls `startup()`, and assigns it to `app.state.service`. See `tests/conftest.py` for the pattern.

Tests hit real pages (e.g., `https://example.com`) via a real headless browser — they are integration tests, not mocks.

## Error Handling

Domain exceptions in `core/errors.py` form a hierarchy under `WebControlError`. The FastAPI app maps them to HTTP status codes in `api/app.py`:

| Exception | HTTP Status |
|-----------|-------------|
| `SessionNotFoundError` | 404 |
| `ElementNotFoundError` | 422 |
| `MaxSessionsError` | 409 |
| `NavigationError` | 502 |
| `ActionError` | 422 |
| `BlockedError` | 409 |
| `SearchNotConfiguredError` | 503 |
| `SearchError` | 502 |

MCP tools catch the same exceptions and return them as error content in the tool response.

## Configuration

All settings via env vars prefixed `WC_` (defined in `config.py`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `WC_PORT` | 8080 | Server port |
| `WC_HOST` | 0.0.0.0 | Bind address |
| `WC_HEADLESS` | true | Headless browser |
| `WC_BROWSER_TYPE` | chromium | Browser engine (chromium/firefox/webkit) |
| `WC_MAX_SESSIONS` | 10 | Max concurrent sessions |
| `WC_DEFAULT_SESSION_TTL_SECONDS` | 1800 | Session idle timeout |
| `WC_VIEWPORT_WIDTH` | 1280 | Default viewport width |
| `WC_VIEWPORT_HEIGHT` | 720 | Default viewport height |
| `WC_NAVIGATION_TIMEOUT_MS` | 30000 | Navigation timeout |
| `WC_ACTION_TIMEOUT_MS` | 10000 | Action timeout |
| `WC_API_KEY` | _(empty)_ | API key for REST auth; empty = open |
| `WC_PROXY_SERVER` | _(empty)_ | HTTP proxy for browser contexts; also enables the proxy escalation tier |
| `WC_PROXY_USERNAME` | _(empty)_ | Proxy auth username |
| `WC_PROXY_PASSWORD` | _(empty)_ | Proxy auth password |
| `WC_STEALTH_ENABLED` | true | Mask headless tells (navigator.webdriver, UA, locale) — tier 0 |
| `WC_USER_AGENT` | _(empty)_ | Override the stealth default user-agent |
| `WC_LOCALE` | en-US | Browser context locale + `Accept-Language` |
| `WC_TIMEZONE_ID` | _(empty)_ | Override browser timezone |
| `WC_NAVIGATION_ESCALATION` | true | Enable the navigate() tier escalation ladder |
| `WC_BEHAVIORAL_JITTER_MS` | 800 | Max random pre-retry delay for the behavioral tier |
| `WC_MAX_TEXT_CONTENT_CHARS` | 8000 | Max chars of body text captured per parse |
| `WC_MAX_INTERACTIVE_ELEMENTS` | 120 | Max interactive elements captured per parse |
| `WC_MAX_FORM_FIELDS` | 60 | Max form fields captured per parse |
| `WC_MAX_LINKS` | 80 | Max links captured per parse |
| `WC_PAGE_SETTLE_ENABLED` | true | Wait for async/JS-rendered content before snapshotting (see core/page_settle.py) |
| `WC_SETTLE_TIMEOUT_MS` | 4000 | Ceiling for networkidle + wait_for_selector during settle |
| `WC_DOM_STABLE_POLLS` | 2 | Consecutive equal DOM-size reads required to consider the page settled |
| `WC_DOM_STABLE_INTERVAL_MS` | 300 | Gap between DOM-stability polls |
| `WC_SCROLL_TO_LOAD_DEFAULT` | false | Auto-scroll on every navigate to trigger lazy content |
| `WC_SCROLL_STEPS` | 8 | Scroll steps when scroll_to_load is on |
| `WC_SCROLL_DELAY_MS` | 250 | Pause between scroll steps |
| `WC_SEARCH_TIER_ENABLED` | false | Enable Tier S search index (needs `WC_SEARCH_API_KEY`) |
| `WC_SEARCH_PROVIDER` | exa | Search provider (exa/brave) |
| `WC_SEARCH_API_KEY` | _(empty)_ | API key for the search provider |
| `WC_NAVIGATION_RETRIES` | 2 | Navigation retry count |
| `WC_ACTION_RETRIES` | 1 | Action retry count |
| `WC_RETRY_DELAY_MS` | 500 | Delay between retries |
| `WC_LOG_LEVEL` | INFO | Log level |
| `WC_LOG_JSON` | false | Structured JSON logging |

## Observability

Five layers — see [docs/observability.md](docs/observability.md) for full details:

1. **Request logging** — every HTTP request with method, path, status, duration (`webcontrol.http` logger)
2. **Correlation IDs** — `x-request-id` header auto-generated or passed through; propagates via contextvars to all log lines
3. **Action timing** — every Playwright action logged with `duration_ms` (INFO for navigate, DEBUG for others)
4. **Session activity log** — per-session deque of last 200 actions; query via `GET /api/v1/sessions/{id}/activity` or `get_session_activity` MCP tool
5. **Playwright tracing** — opt-in per session (`enable_tracing: true`); export as `.zip` for Trace Viewer

Response headers on every request: `x-request-id`, `x-response-time-ms`.

## Documentation

| Doc | When to read |
|-----|--------------|
| [docs/architecture.md](docs/architecture.md) | System design, layers, data flow diagrams, concurrency model |
| [docs/api-reference.md](docs/api-reference.md) | REST endpoints, request/response schemas, PageContent JSON schema |
| [docs/mcp-tools.md](docs/mcp-tools.md) | MCP tool parameters, return types, usage patterns |
| [docs/observability.md](docs/observability.md) | Logging, correlation IDs, timing, activity logs, tracing |
| [docs/robustness.md](docs/robustness.md) | Anti-bot resilience: stealth, block detection, escalation tiers, search fallback |
| [docs/deployment.md](docs/deployment.md) | Docker, local process, launchd, resource planning, security |
| [docs/integration-guide.md](docs/integration-guide.md) | Connecting an LLM agent, Python/TS examples, multi-step flows |
| [mcp-configs/](mcp-configs/README.md) | MCP JSON configs for Claude Desktop, Cursor, Claude Code |
