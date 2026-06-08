from typing import Any, Literal

from pydantic import BaseModel


class NavigateRequest(BaseModel):
    url: str
    wait_until: Literal["load", "domcontentloaded", "networkidle"] = "domcontentloaded"


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
