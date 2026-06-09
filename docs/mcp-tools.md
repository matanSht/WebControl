# MCP Tools Reference

WebControl exposes the following tools via the Model Context Protocol. These are available to any MCP-compatible client (Claude Desktop, Cursor, Claude Code, custom agents).

## Connection Methods

### stdio (local clients)

```bash
webcontrol mcp-stdio
```

Configured in Claude Desktop / Cursor / Claude Code via JSON config:

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

### HTTP (remote / custom agents)

When running `webcontrol serve`, the MCP endpoint is at:

```
http://localhost:8080/mcp
```

Connect using any MCP client SDK that supports Streamable HTTP transport.

---

## Tools

### create_session

Create a new browser session with isolated cookies and storage.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `name` | string | no | null | Human-readable session name |
| `ttl_seconds` | int | no | 1800 | Session idle timeout |
| `viewport_width` | int | no | 1280 | Viewport width |
| `viewport_height` | int | no | 720 | Viewport height |
| `user_agent` | string | no | null | Custom User-Agent |

**Returns:** `SessionInfo` with the session `id`.

---

### list_sessions

List all active browser sessions.

No parameters.

**Returns:** Array of `SessionInfo` objects.

---

### close_session

Close a browser session and release its resources.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | yes | Session ID to close |

**Returns:** Confirmation with session ID.

---

### navigate

Navigate to a URL and return the page content with interactive element refs.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `session_id` | string | yes | — | Target session |
| `url` | string | yes | — | URL to navigate to |
| `wait_until` | string | no | `"domcontentloaded"` | Wait condition |
| `fallback_to_search` | bool | no | `false` | If all browser tiers are blocked, return read-only search-index results instead of an error |
| `wait_for_selector` | string | no | null | Wait until this CSS selector is visible before snapshotting — for JS-rendered content (e.g. `.a-price`) |
| `scroll_to_load` | bool | no | null | Auto-scroll to trigger lazy / on-scroll content before snapshotting |

**Returns:** `ActionResult` with `page_content` plus robustness metadata: `blocked`
(true if an anti-bot wall was detected), `tier_used` (`direct` / `behavioral` /
`proxy` / `search`), `block_reason`, and `search_fallback` (a `SearchResult` when
it fell back to Tier S). If every browser tier is blocked and
`fallback_to_search` is false, the tool reports a Blocked error recommending the
`search` tool. See [robustness.md](robustness.md).

For JS/async-rendered pages, `wait_for_selector` and `scroll_to_load` make
content land before the snapshot; `page_content` also includes `structured_data`
(parsed JSON-LD) and OpenGraph/microdata price tags in `meta`.

---

### get_page_content

Get the current page content without performing any action. Use to re-read the page after waiting or to refresh stale refs.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | yes | Target session |

**Returns:** `PageContent` object.

---

### click

Click an element by its ref ID.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `session_id` | string | yes | — | Target session |
| `ref` | string | yes | — | Element ref (e.g., `"e5"`) |
| `button` | string | no | `"left"` | Mouse button |
| `click_count` | int | no | `1` | Click count |

**Returns:** `ActionResult` with updated `page_content`.

---

### fill

Fill a form field with a value. Clears existing content first.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | yes | Target session |
| `ref` | string | yes | Element ref (must be input/textarea) |
| `value` | string | yes | Text to fill |

**Returns:** `ActionResult` with updated `page_content`.

---

### select

Select a dropdown option.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | yes | Target session |
| `ref` | string | yes | Element ref (must be a select element) |
| `value` | string | yes | Option value or visible text |

**Returns:** `ActionResult` with updated `page_content`.

---

### submit

Submit a form by clicking a submit button or calling form.submit().

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | yes | Target session |
| `ref` | string | yes | Form element or submit button ref |

**Returns:** `ActionResult` with updated `page_content`.

---

### screenshot

Take a PNG screenshot of the current page viewport.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | yes | Target session |

**Returns:** Object with `screenshot_base64` (base64-encoded PNG).

---

### execute_js

Execute JavaScript code on the current page.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | yes | Target session |
| `script` | string | yes | JavaScript code to run |

**Returns:** `ActionResult` with updated `page_content`.

---

### extract

Pull structured rows from the page via CSS selectors — the reliable way to get repeated data (prices, titles, ratings) that the page snapshot truncates or misses. Backed by `eval_on_selector_all`, so it bypasses the text/element caps.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `session_id` | string | yes | — | Target session |
| `selector` | string | yes | — | CSS selector matching each row (e.g. `.s-result-item`) |
| `fields` | array | yes | — | List of `{name, selector?, attribute?}` objects pulled from each row |
| `limit` | int | no | `50` | Max rows (capped by `WC_MAX_EXTRACT_ROWS`) |

Each field: `name` (output key), `selector` (CSS relative to the row; omit for the row itself), `attribute` (e.g. `href`, `content`; omit for text).

**Example:**

```
extract(session_id, selector=".s-result-item", fields=[
  {"name": "title", "selector": "h2"},
  {"name": "price", "selector": ".a-offscreen"},
  {"name": "url", "selector": "a", "attribute": "href"}
])
```

**Returns:** `{selector, count, rows}` — one dict per row; missing target/attribute → `null`; no matches → empty.

---

### get_html

Get the full rendered HTML of the current page (truncated to `WC_HTML_MAX_CHARS`). Full-fidelity fallback when the curated content misses JS-rendered data.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | yes | Target session |

**Returns:** `{url, html, truncated}`.

---

### get_accessibility_tree

Get the page's ARIA snapshot (accessibility tree as YAML) — roles, names, and hierarchy. An alternative full-fidelity view when the curated content snapshot misses something.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | yes | Target session |

**Returns:** `{url, snapshot}`.

---

### configure_network_capture

Start or stop capturing the page's XHR/fetch responses — the deepest extraction lever, recording the raw API JSON behind JS-rendered prices/listings. **Enable before navigating/interacting.**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `session_id` | string | yes | — | Target session |
| `enabled` | bool | no | `true` | Start (`true`) or stop (`false`) capturing |
| `url_filter` | string | no | null | Only capture responses whose URL contains this substring |
| `json_only` | bool | no | `true` | Only capture JSON responses; `false` captures all |

**Returns:** `{enabled, url_filter, json_only}`.

---

### get_network_capture

Get the XHR/fetch responses captured for a session (most recent last). Requires capture to have been enabled before the page loaded.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `session_id` | string | yes | — | Target session |
| `limit` | int | no | `50` | Max responses to return |
| `url_filter` | string | no | null | Further narrow returned responses by URL substring |

**Returns:** `{count, responses}` — each with `url`, `status`, `method`, `resource_type`, `content_type`, and `body` (parsed JSON or capped text).

---

### clear_network_capture

Clear the captured responses for a session.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | yes | Target session |

**Returns:** Confirmation with session ID.

---

### search

Search the web via a pre-crawled search index (Tier S). Reads results from a
search provider's cache **without contacting the target site**, so it bypasses
anti-bot walls (e.g. Amazon's "Continue Shopping" block) that defeat a headless
browser. Use it for read-only info gathering when `navigate` gets blocked or
interaction isn't needed. No session required. Requires
`WC_SEARCH_TIER_ENABLED=true` and `WC_SEARCH_API_KEY`.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | yes | — | Search query |
| `max_results` | int | no | 5 | Max results |
| `fetch_contents` | bool | no | true | Include full extracted page text (Exa) |

**Returns:** `SearchResult` with `results` (title, url, snippet, content, score),
`provider`, and `tier_used`.

---

## Usage Pattern

The typical agent workflow:

```
1. create_session(name="task-x")              → get session_id
2. navigate(session_id, url="https://...")     → see page content
3. [LLM reads elements, decides what to do]
4. fill(session_id, ref="e3", value="...")     → see updated page
5. click(session_id, ref="e7")                → see new page after click
6. [repeat 3-5 as needed]
7. close_session(session_id)                  → cleanup
```

**Important:** Element refs (`e1`, `e2`, ...) are regenerated on every page content response. If you get an `ElementNotFoundError`, the page has changed — call `get_page_content` to get fresh refs.

**For JS-heavy pages** (search results, catalogs, SPAs) where prices/listings render after load, escalate accuracy as needed:

```
1. navigate(..., wait_for_selector=".a-price", scroll_to_load=true)  → content lands before snapshot
2. extract(selector=".s-result-item", fields=[...])                  → exact rows, not a text blob
3. read page_content.structured_data / page_content.meta             → JSON-LD + OG price tags
4. configure_network_capture(...) before navigate, then              → raw API JSON the page fetched
   get_network_capture(...)
5. get_html / get_accessibility_tree                                 → full-fidelity fallback
```

---

## Error Handling

When a tool fails, the response contains an error message. Common errors:

| Error | Meaning | Recovery |
|-------|---------|----------|
| Session not found | Session expired or was closed | Create a new session |
| Element ref not found | Page changed since last read | Call `get_page_content` to get fresh refs |
| Navigation failed | Network timeout or DNS failure | Retry or check URL |
| Blocked | Anti-bot wall after all browser tiers | Use the `search` tool, or retry `navigate` with `fallback_to_search=true` |
| Max sessions reached | Too many open sessions | Close unused sessions first |
| Action failed | Element not interactable | May need to scroll, wait, or try a different element |
