from webcontrol.models.page import PageContent
from webcontrol.models.search import SearchResult

from pydantic import BaseModel


class ActionResult(BaseModel):
    success: bool
    page_content: PageContent | None = None
    error: str | None = None
    # Robustness/escalation metadata. `blocked` is True when an anti-bot wall
    # was detected (even if a page is still returned, so callers never mistake
    # a block page for real content). `tier_used` records which robustness tier
    # produced this result: "direct" | "behavioral" | "proxy" | "search".
    blocked: bool = False
    tier_used: str = "direct"
    block_reason: str | None = None
    # Populated only when navigate() fell back to the search-index tier
    # (fallback_to_search=true and all browser tiers were blocked).
    search_fallback: SearchResult | None = None


class ScreenshotResult(BaseModel):
    success: bool
    screenshot_base64: str | None = None
    error: str | None = None
