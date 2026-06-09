from typing import Any, Literal

from pydantic import BaseModel


class NavigateRequest(BaseModel):
    url: str
    wait_until: Literal["load", "domcontentloaded", "networkidle"] = "domcontentloaded"
    # When the page is blocked by an anti-bot wall, escalate through the
    # robustness tiers (behavioral, proxy) before giving up. See
    # core/navigation_escalation.py.
    escalate: bool = True
    # If every browser tier is still blocked, fall back to the search-index
    # tier (Tier S) and return those results instead of raising BlockedError.
    # Read-only — cannot click or interact. Requires the search tier configured.
    fallback_to_search: bool = False
    # --- content settling (for JS / async-rendered pages) ---
    # Wait for this CSS selector to become visible before snapshotting the DOM
    # (e.g. ".a-price" on a search page whose prices arrive via later XHR).
    wait_for_selector: str | None = None
    # Auto-scroll the page to trigger lazy-loaded / on-scroll content before
    # snapshotting. Recommended for infinite-scroll and search-result pages.
    # None falls back to WC_SCROLL_TO_LOAD_DEFAULT. See core/page_settle.py.
    scroll_to_load: bool | None = None


class ClickRequest(BaseModel):
    ref: str
    click_count: int = 1
    button: Literal["left", "right", "middle"] = "left"


class FillRequest(BaseModel):
    ref: str
    value: str


class SelectRequest(BaseModel):
    ref: str
    value: str


class SubmitRequest(BaseModel):
    ref: str


class ExecuteJsRequest(BaseModel):
    script: str
    args: list[Any] = []


class ExtractField(BaseModel):
    # Output key for this field in each extracted row.
    name: str
    # CSS selector relative to the row element; None reads the row itself.
    selector: str | None = None
    # Attribute to read (e.g. "href", "content"); None reads text content.
    attribute: str | None = None


class ExtractRequest(BaseModel):
    # CSS selector matching each repeated row (e.g. ".s-result-item").
    selector: str
    # Fields to pull from each matched row.
    fields: list[ExtractField]
    # Max rows to return (capped by WC_MAX_EXTRACT_ROWS).
    limit: int = 50


class NetworkCaptureRequest(BaseModel):
    # Start (True) or stop (False) recording XHR/fetch responses for the session.
    enabled: bool = True
    # Only capture responses whose URL contains this substring (None = any URL).
    url_filter: str | None = None
    # Only capture JSON responses (the usual home of API data). False = all.
    json_only: bool = True
