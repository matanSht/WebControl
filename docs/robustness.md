# Navigation Robustness

WebControl drives a real browser at target origins. Sites with anti-bot
infrastructure (Amazon/PerimeterX, Cloudflare, DataDome, Akamai) often serve a
**block page with HTTP 200** instead of content — so a naive `goto()` succeeds
while returning nothing useful. WebControl defends against this with three
things: a hardened browser fingerprint, automatic **block detection**, and an
**escalation ladder** that climbs to stronger strategies and reports honestly
which one was used.

## The tier ladder

```
navigate(url)
   │
   ▼
 direct ──clean─▶ return (tier_used="direct")
   │ blocked
   ▼
 behavioral ──clean─▶ return (tier_used="behavioral")
   │ blocked
   ▼
 proxy ──clean─▶ return (tier_used="proxy")        # only if WC_PROXY_SERVER set
   │ blocked
   ▼
 terminal:
   • fallback_to_search=false (default) → raise BlockedError (HTTP 409)
   • fallback_to_search=true + Tier S on → return search_fallback (tier_used="search")
```

| Tier | `tier_used` | Strategy |
|------|-------------|----------|
| 0 | `direct` | Stealth-hardened context as-is (masked `navigator.webdriver`, real UA, locale/headers — see [stealth](#stealth-tier-0)). Fast path. |
| 1 | `behavioral` | Same page: random jitter delay, `networkidle` settle, scroll + mouse nudge, re-check. |
| 2 | `proxy` | Rebuild the session context through `WC_PROXY_SERVER` (+ rotated UA) to defeat the datacenter-IP signal. **Skipped entirely when no proxy is configured.** |
| S | `search` | Read from a search provider's pre-crawled index ([Tier S](#tier-s--search-index)). The origin is never contacted, so there is no bot wall. Read-only — cannot click or interact. |

## Block detection

`core/block_detection.py` — `detect_block(status, content) -> str | None` is a
pure function run after every navigation attempt. It flags:

- HTTP status in `{403, 429, 503}`.
- Known challenge markers in the title/text (case-insensitive): `robot check`,
  `something went wrong`, `enter the characters you see`, `unusual traffic`,
  `access denied`, `checking your browser`, `captcha`, `px-captcha`, and more.
- Empty challenge shells: no interactive elements + minimal text + a suspicious
  title (`just a moment`, `attention required`, …).

## Honest reporting

Every `navigate` response (`ActionResult`) now carries:

| Field | Meaning |
|-------|---------|
| `blocked` | `true` if an anti-bot wall was detected (even when a page is returned). |
| `tier_used` | Which tier produced this result: `direct` / `behavioral` / `proxy` / `search`. |
| `block_reason` | Why it was flagged (the matched marker or status). `null` when clean. |
| `search_fallback` | A `SearchResult` when navigate fell back to Tier S; otherwise `null`. |

Each tier attempt is also recorded in the session activity log as
`navigate:<tier>`, so escalation is visible via `GET /sessions/{id}/activity`.

## The terminal fallback flag

`NavigateRequest.fallback_to_search` (REST + MCP `navigate(..., fallback_to_search=true)`):

- **false (default):** when all browser tiers are blocked, raise `BlockedError`
  → **HTTP 409**, with a message recommending the `search` tool. Interactive
  semantics stay clean — the caller decides what to do next.
- **true:** when all browser tiers are blocked and Tier S is configured, run the
  search-index tier and return its results in `search_fallback` (`success=true`,
  `blocked=true`, `tier_used="search"`). Read-only.

`escalate=false` disables the ladder entirely — a block at the direct tier raises
immediately.

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `WC_STEALTH_ENABLED` | `true` | Mask headless tells (tier 0). |
| `WC_USER_AGENT` | _(empty)_ | Override the stealth default UA. |
| `WC_LOCALE` | `en-US` | Context locale + `Accept-Language`. |
| `WC_TIMEZONE_ID` | _(empty)_ | Override browser timezone. |
| `WC_NAVIGATION_ESCALATION` | `true` | Enable the escalation ladder. |
| `WC_BEHAVIORAL_JITTER_MS` | `800` | Max random pre-retry delay (tier 1). |
| `WC_PROXY_SERVER` | _(empty)_ | Enables the proxy tier (tier 2) when set. |
| `WC_SEARCH_TIER_ENABLED` | `false` | Enable Tier S (also needs `WC_SEARCH_API_KEY`). |

### Stealth (tier 0)

See `core/stealth.py`. Verified to get Amazon search to HTTP 200 with parsed
result tiles. Not bulletproof — repeated heavy scraping from a datacenter IP can
still trip behavioral checks. Strongest combo: stealth + `WC_HEADLESS=false` +
a residential `WC_PROXY_SERVER`.

### Tier S — search index

See `core/search_tier.py` and the `search` REST endpoint / MCP tool. Queries
Exa or Brave's pre-crawled index and returns titles, URLs, snippets, and (Exa)
full extracted text. Off by default; set `WC_SEARCH_TIER_ENABLED=true` and
`WC_SEARCH_API_KEY`. The most reliable path for read-only data on hostile sites.
