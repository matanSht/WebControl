from webcontrol.models.page import PageContent

from pydantic import BaseModel


class ActionResult(BaseModel):
    success: bool
    page_content: PageContent | None = None
    error: str | None = None


class ScreenshotResult(BaseModel):
    success: bool
    screenshot_base64: str | None = None
    error: str | None = None
