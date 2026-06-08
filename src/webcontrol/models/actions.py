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
