# REST API Reference

Base URL: `http://localhost:8080/api/v1`

All responses use JSON. On error, the response body is `{"error": "description"}`.

If `WC_API_KEY` is set, all endpoints (except `/health`) require the `x-api-key` header.

---

## Sessions

### Create Session

```
POST /sessions
```

**Request body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | no | null | Human-readable session name |
| `ttl_seconds` | int | no | 1800 | Session idle timeout |
| `viewport_width` | int | no | 1280 | Browser viewport width |
| `viewport_height` | int | no | 720 | Browser viewport height |
| `user_agent` | string | no | null | Custom User-Agent string |

**Response (201):**

```json
{
  "id": "a1b2c3d4-...",
  "name": "my-session",
  "created_at": "2025-01-15T10:30:00Z",
  "last_active": "2025-01-15T10:30:00Z",
  "ttl_seconds": 1800,
  "current_url": null,
  "is_alive": true
}
```

**Errors:**
- `409` — Max sessions reached

---

### List Sessions

```
GET /sessions
```

**Response (200):**

```json
[
  {
    "id": "a1b2c3d4-...",
    "name": "my-session",
    "created_at": "2025-01-15T10:30:00Z",
    "last_active": "2025-01-15T10:32:00Z",
    "ttl_seconds": 1800,
    "current_url": "https://example.com/",
    "is_alive": true
  }
]
```

---

### Close Session

```
DELETE /sessions/{session_id}
```

**Response:** `204 No Content`

**Errors:**
- `404` — Session not found

---

## Actions

All action endpoints require a valid `session_id` path parameter.

Every action that modifies the page returns an `ActionResult` containing the updated `PageContent`.

---

### Navigate

```
POST /sessions/{session_id}/navigate
```

**Request body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `url` | string | yes | — | URL to navigate to |
| `wait_until` | string | no | `"domcontentloaded"` | Wait condition: `"load"`, `"domcontentloaded"`, `"networkidle"` |
| `escalate` | bool | no | `true` | Auto-escalate through robustness tiers if the page is blocked |
| `fallback_to_search` | bool | no | `false` | If all browser tiers are blocked, return read-only search-index results instead of a `409` (requires Tier S configured) |
| `wait_for_selector` | string \| null | no | null | Wait until this CSS selector is visible before snapshotting — for content rendered by JS after load (e.g. `.a-price`) |
| `scroll_to_load` | bool \| null | no | null | Auto-scroll the page to trigger lazy / on-scroll content before snapshotting. `null` uses `WC_SCROLL_TO_LOAD_DEFAULT` |

Before parsing, `navigate` runs a bounded **settle** step (networkidle + a DOM-stability poll, plus the optional `wait_for_selector` / `scroll_to_load` above) so JS/async-rendered content lands before the snapshot. See [robustness.md](robustness.md#content-settling).

**Response (200):**

```json
{
  "success": true,
  "page_content": { ... },
  "blocked": false,
  "tier_used": "direct",
  "block_reason": null,
  "search_fallback": null
}
```

| Field | Type | Description |
|-------|------|-------------|
| `blocked` | bool | `true` if an anti-bot wall was detected (even when a page is still returned) |
| `tier_used` | string | Which robustness tier produced this result: `direct` / `behavioral` / `proxy` / `search` |
| `block_reason` | string \| null | Why it was flagged (matched marker or status); `null` when clean |
| `search_fallback` | object \| null | A `SearchResult` when navigate fell back to Tier S; otherwise `null` |

**Errors:**
- `404` — Session not found
- `409` — Blocked: every browser tier was served an anti-bot block page (use the search endpoint, or retry with `fallback_to_search: true`)
- `502` — Navigation failed (timeout, DNS error, etc.)

See [robustness.md](robustness.md) for the escalation ladder and block detection.

---

### Get Page Content

```
GET /sessions/{session_id}/content
```

Returns the current page state without performing any action. Useful for re-reading after an external event or re-parsing after a timeout.

**Response (200):**

```json
{
  "url": "https://example.com/",
  "title": "Example Domain",
  "text_content": "Example Domain This domain is for use in...",
  "elements": [
    {
      "ref": "e1",
      "role": "link",
      "name": "More information...",
      "tag": "a",
      "attributes": {"href": "https://www.iana.org/domains/example"}
    }
  ],
  "forms": [],
  "links": [
    {"ref": "e2", "text": "More information...", "href": "https://www.iana.org/domains/example"}
  ],
  "meta": {"description": "..."},
  "structured_data": [],
  "timestamp": "2025-01-15T10:32:00Z"
}
```

---

### Click

```
POST /sessions/{session_id}/click
```

**Request body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `ref` | string | yes | — | Element ref from page content |
| `button` | string | no | `"left"` | Mouse button: `"left"`, `"right"`, `"middle"` |
| `click_count` | int | no | `1` | Number of clicks (2 for double-click) |

**Response (200):** `ActionResult` with updated `page_content`

**Errors:**
- `404` — Session not found
- `422` — Element ref not found or not interactable

---

### Fill

```
POST /sessions/{session_id}/fill
```

Clears the field and types the new value.

**Request body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `ref` | string | yes | — | Element ref (must be an input/textarea) |
| `value` | string | yes | — | Text to fill |

**Response (200):** `ActionResult` with updated `page_content`

---

### Select

```
POST /sessions/{session_id}/select
```

Select an option from a dropdown/select element.

**Request body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `ref` | string | yes | — | Element ref (must be a select element) |
| `value` | string | yes | — | Option value or visible text |

**Response (200):** `ActionResult` with updated `page_content`

---

### Submit

```
POST /sessions/{session_id}/submit
```

Submits a form. If the ref points to a form element, calls `form.submit()`. If it points to a button, clicks it.

**Request body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `ref` | string | yes | — | Ref to a form element or submit button |

**Response (200):** `ActionResult` with updated `page_content`

---

### Screenshot

```
GET /sessions/{session_id}/screenshot
```

Takes a PNG screenshot of the current viewport.

**Response (200):**

```json
{
  "success": true,
  "screenshot_base64": "iVBORw0KGgoAAAANSUhEUgAA..."
}
```

---

### Execute JavaScript

```
POST /sessions/{session_id}/execute-js
```

Run arbitrary JavaScript on the page.

**Request body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `script` | string | yes | — | JavaScript code to evaluate |
| `args` | array | no | `[]` | Arguments passed to the script |

**Response (200):** `ActionResult` with updated `page_content`

**Errors:**
- `422` — JavaScript execution error

---

## Accurate Extraction

For data rendered by JavaScript (prices, listings, ratings) that the curated `PageContent` truncates or misses, these endpoints read exact values instead of mining the body-text dump. See [integration-guide.md](integration-guide.md#accurate-extraction).

### Extract Structured Rows

```
POST /sessions/{session_id}/extract
```

Pull repeated rows from the page via CSS selectors — backed by `eval_on_selector_all`, so it bypasses the text/element caps entirely.

**Request body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `selector` | string | yes | — | CSS selector matching each row (e.g. `.s-result-item`) |
| `fields` | array | yes | — | Fields to pull from each row (see below) |
| `limit` | int | no | `50` | Max rows (capped by `WC_MAX_EXTRACT_ROWS`) |

Each entry in `fields`:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | yes | — | Output key for the value |
| `selector` | string \| null | no | null | CSS selector relative to the row; omit to use the row element itself |
| `attribute` | string \| null | no | null | Attribute to read (e.g. `href`, `content`); omit to read text content |

**Example request:**

```json
{
  "selector": ".s-result-item",
  "fields": [
    {"name": "title", "selector": "h2"},
    {"name": "price", "selector": ".a-offscreen"},
    {"name": "url", "selector": "a", "attribute": "href"}
  ]
}
```

**Response (200):**

```json
{
  "success": true,
  "selector": ".s-result-item",
  "count": 2,
  "rows": [
    {"title": "Case A", "price": "$12.99", "url": "https://..."},
    {"title": "Case B", "price": "$9.50", "url": "https://..."}
  ],
  "timestamp": "2025-01-15T10:32:00Z"
}
```

A missing field target/attribute yields `null` for that field; no matched rows yields `count: 0` and `rows: []` (never an error).

**Errors:**
- `404` — Session not found
- `422` — Invalid selector / evaluation error

---

### Get Rendered HTML

```
GET /sessions/{session_id}/html
```

Full-fidelity fallback: the page's rendered HTML source, truncated to `WC_HTML_MAX_CHARS`.

**Response (200):**

```json
{
  "success": true,
  "url": "https://example.com/",
  "html": "<!DOCTYPE html><html>...</html>",
  "truncated": false,
  "timestamp": "2025-01-15T10:32:00Z"
}
```

---

### Get Accessibility Tree

```
GET /sessions/{session_id}/accessibility
```

The page's ARIA snapshot (Playwright `aria_snapshot`) as YAML — the semantic structure (roles, names, hierarchy), an alternative full-fidelity view.

**Response (200):**

```json
{
  "success": true,
  "url": "https://example.com/",
  "snapshot": "- heading \"Example Domain\" [level=1]\n- paragraph: ...\n- link \"More information...\"",
  "timestamp": "2025-01-15T10:32:00Z"
}
```

---

## Network Capture

Record the raw XHR/fetch responses a page fetches, so an agent can read the JSON behind JS-rendered data directly. **Disabled per session until enabled.** A `page.on("response")` listener records matching responses into a bounded ring buffer. See [observability.md](observability.md#6-network-capture).

### Configure (start / stop)

```
POST /sessions/{session_id}/network-capture
```

**Request body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `enabled` | bool | no | `true` | Start (`true`) or stop (`false`) capturing |
| `url_filter` | string \| null | no | null | Only capture responses whose URL contains this substring |
| `json_only` | bool | no | `true` | Only capture JSON responses; `false` captures all |

Enable **before** navigating/interacting so the responses are captured as they fire.

**Response (200):**

```json
{"success": true, "enabled": true, "url_filter": "/api/", "json_only": true}
```

### Read

```
GET /sessions/{session_id}/network-capture?limit=50&url_filter=
```

| Query param | Type | Default | Description |
|-------------|------|---------|-------------|
| `limit` | int | `50` | Max responses to return (most recent last) |
| `url_filter` | string \| null | null | Further narrow returned responses by URL substring |

**Response (200):**

```json
{
  "success": true,
  "count": 1,
  "responses": [
    {
      "timestamp": "2025-01-15T10:32:00Z",
      "url": "https://site/api/price",
      "status": 200,
      "method": "GET",
      "resource_type": "fetch",
      "content_type": "application/json",
      "body": {"price": "12.99", "currency": "USD"}
    }
  ],
  "timestamp": "2025-01-15T10:32:00Z"
}
```

`body` is parsed JSON when possible, otherwise capped text (`WC_NETWORK_CAPTURE_MAX_BODY_CHARS`).

### Clear

```
DELETE /sessions/{session_id}/network-capture
```

**Response:** `204 No Content`

---

## Search (Tier S)

```
POST /search
```

Read-only search via a pre-crawled search index (Exa or Brave). The target site
is **never contacted directly**, so anti-bot walls don't apply. No session
required. Cannot click or interact — use it for info gathering when `navigate`
gets blocked. Requires `WC_SEARCH_TIER_ENABLED=true` and `WC_SEARCH_API_KEY`.

**Request body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `query` | string | yes | — | Search query |
| `max_results` | int | no | `WC_SEARCH_MAX_RESULTS` (5) | Max results to return |
| `fetch_contents` | bool | no | `WC_SEARCH_FETCH_CONTENTS` (true) | Include full extracted page text (Exa) |

**Response (200):**

```json
{
  "success": true,
  "query": "iphone 17 case",
  "provider": "exa",
  "tier_used": "search",
  "results": [
    {"title": "...", "url": "https://...", "snippet": "...", "content": "...", "score": 0.83}
  ],
  "timestamp": "2025-01-15T10:32:00Z"
}
```

**Errors:**
- `503` — Search tier not configured (`WC_SEARCH_TIER_ENABLED`/`WC_SEARCH_API_KEY` missing)
- `502` — Search provider request failed

---

## Health Check

```
GET /health
```

Always unauthenticated.

**Response (200):**

```json
{"status": "ok"}
```

---

## Common Error Responses

| Status | Meaning |
|--------|---------|
| `401` | Missing or invalid API key (when `WC_API_KEY` is set) |
| `404` | Session not found |
| `409` | Max sessions reached, or navigation blocked by an anti-bot wall after all tiers |
| `422` | Element not found, not interactable, or JS error |
| `502` | Navigation failed, or search provider error (upstream/network) |
| `503` | Search tier not configured |

---

## PageContent Schema

The `page_content` object returned by actions:

```json
{
  "url": "string — current page URL",
  "title": "string — page title",
  "text_content": "string — visible body text, capped at WC_MAX_TEXT_CONTENT_CHARS (default 8000)",
  "elements": [
    {
      "ref": "e1",
      "role": "button | link | textbox | checkbox | ...",
      "name": "visible text or aria-label",
      "tag": "button | a | input | ...",
      "attributes": {
        "href": "...",
        "type": "...",
        "value": "...",
        "disabled": "true",
        "checked": "true"
      }
    }
  ],
  "forms": [
    {
      "ref": "e5",
      "field_type": "text | email | password | select | checkbox | ...",
      "name": "field name attribute",
      "label": "associated label text",
      "value": "current value",
      "options": ["Option 1", "Option 2"],
      "required": true,
      "placeholder": "Enter email..."
    }
  ],
  "links": [
    {
      "ref": "e8",
      "text": "link text",
      "href": "https://..."
    }
  ],
  "meta": {
    "description": "page meta description",
    "og:title": "OpenGraph title",
    "og:price:amount": "12.99",
    "product:price:amount": "12.99",
    "itemprop:price": "12.99"
  },
  "structured_data": [
    {
      "@type": "Product",
      "name": "Widget",
      "offers": {"@type": "Offer", "price": "12.99", "priceCurrency": "USD"}
    }
  ],
  "timestamp": "2025-01-15T10:32:00Z"
}
```

- `meta` — page metadata: description, OpenGraph (`og:*`), product price tags (`product:price:*`), and microdata expressed as meta tags (`itemprop:*`). Only keys present on the page appear.
- `structured_data` — parsed JSON-LD blobs (`<script type="application/ld+json">`); e-commerce pages embed clean Product/Offer price and rating data here. Capped by `WC_STRUCTURED_DATA_MAX_BLOBS` / `WC_STRUCTURED_DATA_MAX_CHARS`.
