# WebControl

Headless browser automation service for LLM agents. Navigate pages, read structured content, click elements, fill forms — all through a REST API or MCP (Model Context Protocol) tools.

## How It Works

```
┌──────────────────────────┐
│       LLM Agent          │
│  (Claude, custom, etc.)  │
└────────────┬─────────────┘
             │  1. navigate("https://example.com")
             │  2. receives PageContent with element refs (e1, e2, e3...)
             │  3. fill("e3", "user@example.com")
             │  4. click("e7")
             │  5. receives updated PageContent
             ▼
┌──────────────────────────┐
│      WebControl          │
│  REST API + MCP Server   │
│  (single process/port)   │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│  Playwright (headless)   │
│  Chromium browser        │
└──────────────────────────┘
```

The LLM reads a compact structured representation of the page (interactive elements, forms, links — not raw HTML), decides what to do, and sends an action. WebControl executes it and returns the new page state.

## Quick Start

### Local

```bash
# Install
python3 -m venv .venv && source .venv/bin/activate
pip install ".[dev]"
playwright install chromium

# Run
webcontrol serve
```

Server starts at `http://localhost:8080`. Try the health check:

```bash
curl http://localhost:8080/health
```

### Docker

```bash
docker compose up --build
```

## Usage

### REST API

```bash
# Create a session
curl -X POST http://localhost:8080/api/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{"name": "my-task"}'
# Returns: {"id": "abc-123", "name": "my-task", ...}

# Navigate
curl -X POST http://localhost:8080/api/v1/sessions/abc-123/navigate \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'
# Returns: {"success": true, "page_content": {"elements": [...], "forms": [...], ...}}

# Fill a form field (using ref from page_content)
curl -X POST http://localhost:8080/api/v1/sessions/abc-123/fill \
  -H "Content-Type: application/json" \
  -d '{"ref": "e3", "value": "hello@example.com"}'

# Click an element
curl -X POST http://localhost:8080/api/v1/sessions/abc-123/click \
  -H "Content-Type: application/json" \
  -d '{"ref": "e7"}'

# Close session when done
curl -X DELETE http://localhost:8080/api/v1/sessions/abc-123
```

### MCP (Model Context Protocol)

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "webcontrol": {
      "command": "webcontrol",
      "args": ["mcp-stdio"]
    }
  }
}
```

For Cursor, add to `.cursor/mcp.json` in your project. See `mcp-configs/` for more examples.

Once configured, the LLM gets these tools: `create_session`, `navigate`, `get_page_content`, `click`, `fill`, `select`, `submit`, `screenshot`, `execute_js`, `close_session`.

## Configuration

All settings via environment variables prefixed `WC_`:

| Variable | Default | Description |
|----------|---------|-------------|
| `WC_PORT` | `8080` | Server port |
| `WC_HOST` | `0.0.0.0` | Bind address |
| `WC_HEADLESS` | `true` | Run browser headless |
| `WC_BROWSER_TYPE` | `chromium` | Browser engine (`chromium`, `firefox`, `webkit`) |
| `WC_MAX_SESSIONS` | `10` | Maximum concurrent browser sessions |
| `WC_DEFAULT_SESSION_TTL_SECONDS` | `1800` | Session idle timeout (30 min) |
| `WC_VIEWPORT_WIDTH` | `1280` | Default viewport width |
| `WC_VIEWPORT_HEIGHT` | `720` | Default viewport height |
| `WC_NAVIGATION_TIMEOUT_MS` | `30000` | Navigation timeout |
| `WC_ACTION_TIMEOUT_MS` | `10000` | Action timeout (click, fill, etc.) |
| `WC_API_KEY` | _(empty)_ | API key for REST auth; empty = no auth |
| `WC_PROXY_SERVER` | _(empty)_ | HTTP proxy (e.g., `http://proxy:8080`) |
| `WC_PROXY_USERNAME` | _(empty)_ | Proxy auth username |
| `WC_PROXY_PASSWORD` | _(empty)_ | Proxy auth password |
| `WC_NAVIGATION_RETRIES` | `2` | Retry attempts for navigation |
| `WC_ACTION_RETRIES` | `1` | Retry attempts for actions |
| `WC_RETRY_DELAY_MS` | `500` | Delay between retries |
| `WC_LOG_LEVEL` | `INFO` | Log level |
| `WC_LOG_JSON` | `false` | Output structured JSON logs |

## Authentication

Set `WC_API_KEY` to enable API key authentication on REST endpoints:

```bash
export WC_API_KEY="your-secret-key"
webcontrol serve
```

Clients must include the key in requests:

```bash
curl -H "x-api-key: your-secret-key" http://localhost:8080/api/v1/sessions
```

The `/health` endpoint is always unauthenticated.

MCP stdio mode does not use HTTP auth (it runs as a local subprocess).

## Development

```bash
# Run tests
pytest tests/ -v

# Run a single test
pytest tests/test_api/test_routes.py::test_navigate_and_get_content -v

# Lint
ruff check src/ tests/

# Format
ruff format src/ tests/
```

## License

MIT
