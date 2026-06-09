# Observability

WebControl provides six layers of observability for debugging, performance analysis, and troubleshooting.

## 1. Request Logging

Every HTTP request is logged with method, path, status code, duration, and session ID.

**Human-readable output** (default):

```
10:32:15 INFO     [webcontrol.http] POST /api/v1/sessions/abc-123/navigate → 200 (1523.4ms) session=abc-123
10:32:16 INFO     [webcontrol.http] GET /api/v1/sessions/abc-123/content → 200 (45.2ms) session=abc-123
```

**JSON output** (`WC_LOG_JSON=true`):

```json
{
  "timestamp": "2025-01-15T10:32:15.123Z",
  "level": "INFO",
  "logger": "webcontrol.http",
  "message": "POST /api/v1/sessions/abc-123/navigate → 200 (1523.4ms) session=abc-123",
  "request_id": "a3f2b1c8"
}
```

**Response headers** on every request:

| Header | Description |
|--------|-------------|
| `x-request-id` | Correlation ID (auto-generated or echoed from request) |
| `x-response-time-ms` | Total request duration in milliseconds |

## 2. Correlation IDs

Every request gets an 8-character correlation ID that propagates through all log messages in that request's call chain.

**Auto-generated:** If no `x-request-id` header is sent, one is generated.

**Pass-through:** Send `x-request-id: my-trace-42` and it will appear in all logs and be echoed in the response header.

This lets you trace a single request across all log lines:

```
10:32:15 INFO     [webcontrol.http] [a3f2b1c8] POST /api/v1/sessions/abc/navigate → 200 (1523.4ms)
10:32:15 INFO     [webcontrol.actions] [a3f2b1c8] navigate url=https://example.com elements=5 forms=0 duration_ms=1480.2
10:32:15 DEBUG    [webcontrol.parser] [a3f2b1c8] parse url=https://example.com/ elements=5 forms=0 links=1 refs=6 duration_ms=42.1
```

## 3. Action Timing

Every action (navigate, click, fill, etc.) is timed and logged with performance metrics.

**Log levels:**
- `INFO` — navigation (most expensive operation)
- `DEBUG` — all other actions (click, fill, select, submit, screenshot, get_page_content)

**What's measured:**
- Total action duration (includes Playwright execution + page re-parse)
- Page parse duration (DOM queries + ref assignment)
- Retry attempts and delays

**Enable DEBUG to see all action timing:**

```bash
WC_LOG_LEVEL=DEBUG webcontrol serve
```

**Example output at DEBUG:**

```
10:32:15 INFO     [webcontrol.actions] navigate url=https://example.com elements=5 forms=0 duration_ms=1480.2
10:32:15 DEBUG    [webcontrol.parser] parse url=https://example.com/ elements=5 forms=0 links=1 refs=6 duration_ms=42.1
10:32:16 DEBUG    [webcontrol.actions] click ref=e3 duration_ms=230.5
10:32:16 DEBUG    [webcontrol.parser] parse url=https://example.com/next elements=12 forms=2 links=8 refs=22 duration_ms=65.3
10:32:17 DEBUG    [webcontrol.actions] fill ref=e5 duration_ms=85.1
10:32:17 DEBUG    [webcontrol.actions] screenshot size_bytes=145320 duration_ms=120.8
```

**Retry logging** (WARNING level):

```
10:32:15 WARNING  [webcontrol.retry] navigate(https://slow-site.com) failed (attempt 1/3): Timeout 30000ms exceeded — retrying in 500ms
10:32:46 WARNING  [webcontrol.retry] navigate(https://slow-site.com) failed (attempt 2/3): Timeout 30000ms exceeded — retrying in 500ms
10:32:46 ERROR    [webcontrol.retry] navigate(https://slow-site.com) failed after 3 attempts: Timeout 30000ms exceeded
```

## 4. Session Activity Log

Each session maintains an ordered log of all actions performed (last 200 entries). Query it via API or MCP.

### REST API

```bash
# Get action history
curl http://localhost:8080/api/v1/sessions/{id}/activity?limit=20

# Get aggregated stats
curl http://localhost:8080/api/v1/sessions/{id}/stats
```

### MCP Tools

```
get_session_activity(session_id, limit=50)
get_session_stats(session_id)
```

### Activity Entry Format

```json
{
  "timestamp": "2025-01-15T10:32:15.123Z",
  "action": "navigate",
  "url": "https://example.com",
  "duration_ms": 1523.4,
  "success": true
}
```

```json
{
  "timestamp": "2025-01-15T10:32:16.456Z",
  "action": "click",
  "ref": "e3",
  "duration_ms": 230.5,
  "success": true
}
```

```json
{
  "timestamp": "2025-01-15T10:32:17.789Z",
  "action": "fill",
  "ref": "e5",
  "duration_ms": 85.1,
  "success": false,
  "error": "Element not interactable"
}
```

### Stats Format

```json
{
  "total_actions": 15,
  "success_count": 14,
  "error_count": 1,
  "avg_duration_ms": 342.5,
  "max_duration_ms": 1523.4,
  "min_duration_ms": 42.1
}
```

## 5. Playwright Tracing

For deep debugging, enable Playwright tracing on a session. This records screenshots, DOM snapshots, and network activity at every step — viewable in [Playwright Trace Viewer](https://trace.playwright.dev).

### Enable Tracing

Pass `enable_tracing: true` when creating a session:

**REST:**

```bash
curl -X POST http://localhost:8080/api/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{"name": "debug-session", "enable_tracing": true}'
```

**MCP:**

```
create_session(name="debug-session", enable_tracing=true)
```

### Export Trace

Download the trace as a `.zip` file:

```bash
curl -X POST http://localhost:8080/api/v1/sessions/{id}/trace/export \
  --output trace.zip
```

### View Trace

Open the trace in the Playwright Trace Viewer:

```bash
npx playwright show-trace trace.zip
```

Or upload to https://trace.playwright.dev

The trace shows:
- Screenshots at each action
- DOM snapshots (inspect elements at any point)
- Network requests and responses
- Console messages
- Action timeline with durations

### Performance Note

Tracing adds overhead (~10-20% slower actions due to snapshot capture). Only enable it for debugging, not production use.

## 6. Network Capture

Record the raw XHR/fetch responses a page fetches, so an agent (or you) can read the JSON behind JS-rendered data instead of scraping the DOM. **Disabled per session until enabled.** When on, a `page.on("response")` listener (`observability/network.py`) records responses matching the filters into a bounded ring buffer; bodies are read on background tasks, and a read first drains in-flight reads so the snapshot is complete.

Capture survives proxy-tier context rebuilds (the listener is re-attached). Filtering is cheap-first: a disabled or non-matching response never spawns a body read.

### Enable, Read, Clear

**REST:**

```bash
# Start (enable BEFORE navigating). json_only=true keeps only JSON responses.
curl -X POST http://localhost:8080/api/v1/sessions/{id}/network-capture \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "url_filter": "/api/", "json_only": true}'

# ... navigate / interact ...

# Read captured responses (most recent last)
curl "http://localhost:8080/api/v1/sessions/{id}/network-capture?limit=20"

# Stop / clear
curl -X POST http://localhost:8080/api/v1/sessions/{id}/network-capture -d '{"enabled": false}'
curl -X DELETE http://localhost:8080/api/v1/sessions/{id}/network-capture
```

**MCP tools:**

```
configure_network_capture(session_id, enabled=true, url_filter="/api/", json_only=true)
get_network_capture(session_id, limit=50, url_filter=None)
clear_network_capture(session_id)
```

### Captured Response Format

```json
{
  "timestamp": "2025-01-15T10:32:00Z",
  "url": "https://site/api/price",
  "status": 200,
  "method": "GET",
  "resource_type": "fetch",
  "content_type": "application/json",
  "body": {"price": "12.99", "currency": "USD"}
}
```

`body` is parsed JSON when possible, otherwise capped text. Bound the buffer and bodies with `WC_NETWORK_CAPTURE_MAX_ENTRIES` (default 50) and `WC_NETWORK_CAPTURE_MAX_BODY_CHARS` (default 100000).

### When to Use

- The data you want renders via XHR/fetch and isn't in the DOM snapshot (or is truncated).
- You want the source values (exact price/currency/stock) rather than formatted display text.
- You're reverse-engineering a site's internal API to read data directly.

---

## Logger Hierarchy

| Logger | Level | Content |
|--------|-------|---------|
| `webcontrol.http` | INFO | Every HTTP request with method, path, status, duration |
| `webcontrol.sessions` | INFO | Session create, close, expire events |
| `webcontrol.actions` | INFO/DEBUG | Action execution with timing and element counts |
| `webcontrol.escalation` | INFO | Per-tier navigation attempts (`navigate tier=… blocked=…`) |
| `webcontrol.settle` | DEBUG | Content-settle steps (selector wait, scroll, networkidle, DOM stability) |
| `webcontrol.parser` | DEBUG | Page parse duration and element/form/link counts |
| `webcontrol.retry` | WARNING/ERROR | Retry attempts and final failures |

## Troubleshooting Recipes

### "Why is this page slow?"

1. Set `WC_LOG_LEVEL=DEBUG`
2. Navigate to the page
3. Look at `webcontrol.parser` logs — is parse time high? (complex DOM)
4. Look at `webcontrol.actions` navigate duration — is it the network?
5. Check `/stats` — is `max_duration_ms` an outlier or consistent?

### "Why did this action fail?"

1. Check `/activity` for the session — find the failed entry with `"success": false`
2. The `error` field shows the Playwright error message
3. If it's `ElementNotFoundError` — the page changed between read and action
4. If it's a timeout — try increasing `WC_ACTION_TIMEOUT_MS`
5. For deep debugging: recreate with `enable_tracing: true` and export the trace

### "What did this session do?"

```bash
curl http://localhost:8080/api/v1/sessions/{id}/activity?limit=200
```

Shows a full timeline of every action, with timestamps, durations, and success/failure.

### "Is the service healthy?"

```bash
# Basic health
curl http://localhost:8080/health

# Active sessions and their URLs
curl http://localhost:8080/api/v1/sessions

# Per-session performance
curl http://localhost:8080/api/v1/sessions/{id}/stats
```
