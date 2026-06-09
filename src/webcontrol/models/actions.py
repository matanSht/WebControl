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
