# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WebControl is a headless browser automation service for LLM agents. It navigates pages, reads structured content, and interacts with elements (click, fill, select, submit) — exposed via both a REST API and MCP (Model Context Protocol) server on a single port.

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
    SessionManager     ← BrowserSession per caller (core/session_manager.py)
    PageParser         ← DOM → PageContent with refs e1..eN (core/page_parser.py)
    ActionExecutor     ← ref → Locator, execute with retry (core/action_executor.py)
              ↓
    BrowserManager     ← single Playwright Browser instance (core/browser_manager.py)
```

**Dual API, shared core.** REST routes (`api/routes_*.py`) and MCP tools (`mcp_server/server.py`) are thin wrappers over the same `WebControlService`. They share browser sessions and state in one process.

**Element ref system.** `PageParser` queries the DOM for visible interactive elements, assigns short refs (`e1`–`eN`), and stores a `dict[str, Locator]` in `BrowserSession.ref_map`. Every action response includes fresh `PageContent` with new refs. If a ref is stale, `ActionExecutor` raises `ElementNotFoundError`.

**Session isolation.** One Playwright `BrowserContext` per session (separate cookies, storage, cache). Per-session `asyncio.Lock` serializes actions within a session; different sessions run concurrently. Background cleanup evicts sessions past TTL.

**Retry.** `core/retry.py` wraps Playwright calls with configurable retries on transient errors.

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
| `WC_PROXY_SERVER` | _(empty)_ | HTTP proxy for browser contexts |
| `WC_PROXY_USERNAME` | _(empty)_ | Proxy auth username |
| `WC_PROXY_PASSWORD` | _(empty)_ | Proxy auth password |
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
| [docs/deployment.md](docs/deployment.md) | Docker, local process, launchd, resource planning, security |
| [docs/integration-guide.md](docs/integration-guide.md) | Connecting an LLM agent, Python/TS examples, multi-step flows |
| [mcp-configs/](mcp-configs/README.md) | MCP JSON configs for Claude Desktop, Cursor, Claude Code |
