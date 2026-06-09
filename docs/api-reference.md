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
  "text_content": "string — visible body text, max ~4000 chars",
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
    "description": "page meta description"
  },
  "timestamp": "2025-01-15T10:32:00Z"
}
```
