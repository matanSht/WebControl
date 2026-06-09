# LLM Agent Integration Guide

This document explains how to connect WebControl to an LLM agent as a tool.

## The Interaction Loop

WebControl follows a simple cycle:

```
┌─────────────────────────────────────────────────┐
│  1. Agent asks WebControl to load a page        │
│  2. WebControl returns structured page content  │
│  3. Agent reads content, decides next action    │
│  4. Agent tells WebControl what to do           │
│  5. WebControl executes, returns new state      │
│  6. Repeat from step 3 until task is done       │
└─────────────────────────────────────────────────┘
```

## Integration Option A: MCP (Recommended for Claude)

### Setup

1. Install WebControl and ensure `webcontrol` is on your PATH
2. Add to your MCP client config (see `mcp-configs/`)
3. The LLM automatically sees the tools and can call them

### Example Conversation

With MCP configured, you can prompt Claude like:

> "Go to https://news.ycombinator.com, find the top 3 stories, and tell me their titles and point counts."

Claude will:
1. Call `create_session`
2. Call `navigate` with the URL
3. Read the `page_content` to find story elements
4. Extract the information
5. Call `close_session`
6. Report the results

### Example: Form Submission

> "Go to https://httpbin.org/forms/post and fill out the form with test data, then submit it."

Claude will:
1. `create_session` → session_id
2. `navigate(session_id, "https://httpbin.org/forms/post")` → sees form fields in `page_content.forms`
3. `fill(session_id, "e3", "John")` → fills the name field
4. `fill(session_id, "e4", "john@test.com")` → fills email
5. `submit(session_id, "e8")` → submits the form
6. Reads the result page
7. `close_session(session_id)` → cleanup

---

## Integration Option B: REST API (Custom Orchestrators)

### Python Example

```python
import httpx

BASE = "http://localhost:8080/api/v1"
HEADERS = {"x-api-key": "your-key"}  # omit if no auth


async def browse_and_extract():
    async with httpx.AsyncClient(base_url=BASE, headers=HEADERS) as client:
        # Create session
        resp = await client.post("/sessions", json={"name": "scrape-task"})
        session_id = resp.json()["id"]

        # Navigate
        resp = await client.post(
            f"/sessions/{session_id}/navigate",
            json={"url": "https://example.com"},
        )
        page = resp.json()["page_content"]

        # Read the page content — send to LLM for decision
        # page["elements"] has interactive elements
        # page["forms"] has form fields
        # page["links"] has links
        # page["text_content"] has visible text

        # ... LLM decides to click element "e1" ...

        resp = await client.post(
            f"/sessions/{session_id}/click",
            json={"ref": "e1"},
        )
        new_page = resp.json()["page_content"]

        # Cleanup
        await client.delete(f"/sessions/{session_id}")

        return new_page
```

### TypeScript Example

```typescript
const BASE = "http://localhost:8080/api/v1";

async function browse() {
  // Create session
  const session = await fetch(`${BASE}/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: "task" }),
  }).then((r) => r.json());

  // Navigate
  const result = await fetch(`${BASE}/sessions/${session.id}/navigate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: "https://example.com" }),
  }).then((r) => r.json());

  // result.page_content has elements, forms, links, text_content
  console.log(result.page_content.elements);

  // Cleanup
  await fetch(`${BASE}/sessions/${session.id}`, { method: "DELETE" });
}
```

---

## Integration Option C: HTTP MCP Transport (Custom MCP Clients)

If your agent framework supports MCP over HTTP:

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def connect():
    async with streamablehttp_client("http://localhost:8080/mcp") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # List available tools
            tools = await session.list_tools()

            # Call a tool
            result = await session.call_tool("navigate", {
                "session_id": "...",
                "url": "https://example.com",
            })
```

---

## Understanding PageContent

When you receive `page_content`, here's how to interpret it for the LLM:

### Elements

Interactive elements the user can interact with:

```json
{
  "ref": "e1",
  "role": "button",
  "name": "Sign In",
  "tag": "button",
  "attributes": {}
}
```

The `ref` is what you pass to `click`, `fill`, `select`, or `submit`.

### Forms

Form fields with their current state:

```json
{
  "ref": "e3",
  "field_type": "email",
  "name": "email",
  "label": "Email Address",
  "value": "",
  "options": [],
  "required": true,
  "placeholder": "Enter your email"
}
```

### Links

Navigable links:

```json
{
  "ref": "e8",
  "text": "About Us",
  "href": "/about"
}
```

### Text Content

The visible text of the page (capped at `WC_MAX_TEXT_CONTENT_CHARS`, default 8000). Useful for reading articles, extracting data, or understanding context.

### Structured Data & Meta

`page_content.structured_data` holds parsed JSON-LD blobs and `page_content.meta` holds OpenGraph/microdata tags — including price fields (`og:price:amount`, `product:price:amount`, `itemprop:price`) and Product/Offer schema. For e-commerce pages this is often the cleanest source of price and rating data, no scraping required.

---

## Accurate Extraction

The curated `PageContent` caps body text and element counts, and prices/listings
on JS-heavy pages may not be in the DOM when navigate returns. WebControl offers
a ladder of progressively stronger ways to get exact data — use the lightest one
that works:

1. **Settle the page.** `navigate(..., wait_for_selector=".a-price", scroll_to_load=true)`
   waits for async content and fires lazy loaders before the snapshot.
2. **Read embedded data.** Check `page_content.structured_data` (JSON-LD) and
   `page_content.meta` (OpenGraph/microdata price tags) first.
3. **Extract structured rows.** `extract` pulls exact fields from every matching
   row via CSS selectors — bypasses truncation entirely:

   ```python
   resp = await client.post(
       f"/sessions/{session_id}/extract",
       json={
           "selector": ".s-result-item",
           "fields": [
               {"name": "title", "selector": "h2"},
               {"name": "price", "selector": ".a-offscreen"},
               {"name": "rating", "selector": ".a-icon-alt"},
               {"name": "url", "selector": "a", "attribute": "href"},
           ],
       },
   )
   rows = resp.json()["rows"]
   ```

4. **Capture the API.** Enable network capture *before* navigating, then read the
   raw JSON the page fetched — the source behind the rendered values:

   ```python
   await client.post(f"/sessions/{session_id}/network-capture",
                     json={"enabled": True, "url_filter": "/api/", "json_only": True})
   await client.post(f"/sessions/{session_id}/navigate", json={"url": "https://..."})
   captured = (await client.get(f"/sessions/{session_id}/network-capture")).json()["responses"]
   ```

5. **Full-fidelity fallback.** `GET /sessions/{id}/html` (rendered HTML) or
   `GET /sessions/{id}/accessibility` (ARIA snapshot) when all else misses it.

See [api-reference.md](api-reference.md#accurate-extraction) for full schemas.

---

## Tips for LLM Prompts

When building agent prompts that use WebControl:

1. **Tell the LLM about refs:** "Each interactive element has a `ref` like `e1`, `e2`. Use these refs when calling click, fill, or submit."

2. **Handle stale refs:** "If you get an ElementNotFoundError, the page has changed. Call get_page_content to get fresh refs before retrying."

3. **Be specific about goals:** "Navigate to X, find the Y field, fill it with Z, then click Submit."

4. **Session lifecycle:** "Always close_session when done to free resources."

5. **Prefer forms over elements:** "Check `forms` first for input fields — it includes labels and types. Use `elements` for buttons and interactive widgets."

6. **Watch for blocks:** "Check `blocked` and `tier_used` on navigate responses. If `blocked` is true or you get a Blocked error, the site has an anti-bot wall — switch to the `search` tool for read-only info, or retry navigate with `fallback_to_search: true`."

---

## Multi-Step Flows

For complex tasks (login → navigate → extract):

```
1. create_session (with TTL long enough for the flow)
2. navigate to login page
3. fill username field
4. fill password field
5. click sign-in button
6. wait for redirect (navigate or get_page_content)
7. navigate to target page
8. extract needed data from page_content
9. close_session
```

The session preserves cookies between steps, so the login persists through the flow.

---

## Error Recovery

| Situation | Solution |
|-----------|----------|
| Element ref not found | Call `get_page_content` to refresh refs |
| Navigation timeout | Retry with `wait_until: "load"` or increase timeout |
| Session expired | Create a new session and restart the flow |
| Page requires JavaScript wait | Navigate with `wait_for_selector` for the content you need (or `execute_js` to wait, then `get_page_content`) |
| Data rendered after load is missing | Navigate with `scroll_to_load: true` / `wait_for_selector`; then `extract`, read `structured_data`, or use network capture |
| Site blocked by anti-bot wall | Use the `search` tool, or retry navigate with `fallback_to_search: true` |
| Element not visible | May need to scroll — navigate with `scroll_to_load: true`, or `execute_js("window.scrollBy(0, 500)")` then retry |
