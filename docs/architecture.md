# Architecture

## System Overview

WebControl is a single-process Python service that manages headless browser instances and exposes them to LLM agents through two transports:

1. **REST API** — standard HTTP at `/api/v1/...`
2. **MCP Server** — Model Context Protocol at `/mcp` (HTTP) or stdio

Both share the same `WebControlService` facade and in-memory session store. A single Chromium browser process serves all sessions.

```
┌─────────────────────────────────────────────────────────────┐
│                        Process                               │
│                                                             │
│  ┌─────────────┐    ┌──────────────┐                       │
│  │  MCP Server │    │  FastAPI App │                       │
│  │  (tools)    │    │  (routes)    │                       │
│  └──────┬──────┘    └──────┬───────┘                       │
│         │                  │                               │
│         └────────┬─────────┘                               │
│                  ▼                                          │
│  ┌───────────────────────────────┐                         │
│  │     WebControlService         │  ← Facade               │
│  │     (core/service.py)         │                         │
│  └───────────────┬───────────────┘                         │
│                  │                                          │
│  ┌───────────────┼───────────────────────────────────┐     │
│  │               │         Core Layer                 │     │
│  │  ┌────────────▼────────────┐                      │     │
│  │  │    SessionManager       │                      │     │
│  │  │  - session CRUD         │                      │     │
│  │  │  - TTL cleanup loop     │                      │     │
│  │  │  - per-session locks    │                      │     │
│  │  └────────────┬────────────┘                      │     │
│  │               │                                    │     │
│  │  ┌────────────▼────────────┐  ┌────────────────┐ │     │
│  │  │    ActionExecutor       │  │  PageParser    │ │     │
│  │  │  - ref → locator        │  │  - DOM queries │ │     │
│  │  │  - retry logic          │──│  - ref assign  │ │     │
│  │  │  - click/fill/submit    │  │  - forms/links │ │     │
│  │  └────────────┬────────────┘  └────────────────┘ │     │
│  │               │                                    │     │
│  │  ┌────────────▼────────────┐                      │     │
│  │  │    BrowserManager       │                      │     │
│  │  │  - single Browser       │                      │     │
│  │  │  - Playwright lifecycle │                      │     │
│  │  └────────────────────────┘                      │     │
│  └───────────────────────────────────────────────────┘     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Layers

### Transport Layer (`api/` and `mcp_server/`)

Thin adapters that parse incoming requests and call `WebControlService` methods. They handle:
- Request/response serialization
- Error-to-HTTP-status mapping (REST)
- Error-to-tool-response mapping (MCP)
- API key authentication (REST only, via middleware)

### Service Facade (`core/service.py`)

Single entry point composing all core components. Owns:
- Lifecycle (`startup()`/`shutdown()`)
- Session lookup + lock acquisition pattern
- Delegation to executor

### Core Components

| Component | File | Responsibility |
|-----------|------|----------------|
| `BrowserManager` | `core/browser_manager.py` | Owns the single Playwright `Browser` instance. Launches on startup, closes on shutdown. |
| `SessionManager` | `core/session_manager.py` | CRUD for `BrowserSession` objects. Background TTL cleanup. Proxy configuration. Attaches the per-session network-capture listener. |
| `NavigationEscalator` | `core/navigation_escalation.py` | Runs `navigate()` through the robustness tier ladder with block detection; builds settle options per request. |
| `PageSettle` | `core/page_settle.py` | Bounded wait for async/JS-rendered content before a snapshot (selector wait, scroll, networkidle, DOM-stability poll). |
| `PageParser` | `core/page_parser.py` | Queries the DOM for interactive elements, forms, and links. Assigns refs. Harvests JSON-LD + OpenGraph/microdata. Builds `PageContent`. |
| `ActionExecutor` | `core/action_executor.py` | Resolves refs to Playwright Locators. Executes actions with retry. Returns fresh `PageContent`. Also: targeted `extract`, `get_html`, `get_accessibility_tree`. |
| `NetworkCapture` | `observability/network.py` | Per-session ring buffer of captured XHR/fetch responses (opt-in), for reading raw API payloads. |
| `SearchTier` | `core/search_tier.py` | Tier S: read-only results from a search provider's pre-crawled index (no origin contact). |

## Key Design Decisions

### Element References

Elements are identified by short refs (`e1`, `e2`, ..., `eN`) rather than CSS selectors or XPaths.

**Why:**
- Token-efficient for LLMs (2-4 chars vs. 50+ char selectors)
- No ambiguity — each ref maps to exactly one element
- Resilient to DOM changes between the parse and the action (the Locator handles retries)

**How:**
- `PageParser` walks the DOM, finds visible interactive elements
- Assigns monotonic refs (`e1`, `e2`, ...)
- Stores a `dict[str, Locator]` in `BrowserSession.ref_map`
- `ActionExecutor` looks up the ref to get the Locator
- If ref is missing → `ElementNotFoundError` (page changed, caller should re-read)

### Session Isolation

Each session gets its own Playwright `BrowserContext`:
- Cookies, localStorage, and cache are fully isolated
- One session's login doesn't leak to another
- Sessions can run concurrently (different contexts)
- Actions within a single session are serialized (asyncio.Lock)

### Retry Strategy

Transient Playwright errors (network timeouts, element temporarily obscured) are retried:
- Navigation: 2 retries by default
- Actions (click, fill, select): 1 retry by default
- Configurable via `WC_NAVIGATION_RETRIES`, `WC_ACTION_RETRIES`, `WC_RETRY_DELAY_MS`

### Single Process Model

REST API and MCP server run in the same async process:
- No inter-process communication needed
- Shared session store means an agent can create a session via REST and use it via MCP (or vice versa)
- Simpler deployment (one container, one port)

## Data Flow

### Navigate + Read

```
Agent                    WebControl                    Browser
  │                         │                            │
  │── navigate(url) ───────>│                            │
  │                         │── page.goto(url) ─────────>│
  │                         │<── page loaded ────────────│
  │                         │── query interactive els ──>│
  │                         │<── elements + locators ────│
  │                         │── assign refs (e1..eN) ───>│ (in memory)
  │                         │── build PageContent ──────>│ (in memory)
  │<── ActionResult ────────│                            │
  │    (with PageContent)   │                            │
```

### Click

```
Agent                    WebControl                    Browser
  │                         │                            │
  │── click("e5") ─────────>│                            │
  │                         │── ref_map["e5"] ──────────>│ (lookup Locator)
  │                         │── locator.click() ────────>│
  │                         │<── done ──────────────────│
  │                         │── re-parse page ──────────>│
  │                         │<── new PageContent ───────│
  │<── ActionResult ────────│                            │
  │    (with new content)   │                            │
```

## Concurrency Model

```
Session A ─── Lock A ─── action 1 → action 2 → action 3 (sequential)
Session B ─── Lock B ─── action 1 → action 2            (concurrent with A)
Session C ─── Lock C ─── action 1                       (concurrent with A and B)
```

- Different sessions execute in parallel (different browser contexts)
- Actions within one session are serialized (prevents race conditions on a single page)
- The cleanup loop runs independently, checking all sessions every 60 seconds
