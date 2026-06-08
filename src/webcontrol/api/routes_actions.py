from fastapi import APIRouter, Depends

from webcontrol.api.dependencies import get_service
from webcontrol.core.service import WebControlService
from webcontrol.models.actions import (
    ClickRequest,
    ExecuteJsRequest,
    FillRequest,
    NavigateRequest,
    SelectRequest,
    SubmitRequest,
)
from webcontrol.models.page import PageContent
from webcontrol.models.responses import ActionResult, ScreenshotResult

router = APIRouter(prefix="/sessions/{session_id}", tags=["actions"])


@router.post("/navigate", response_model=ActionResult)
async def navigate(
    session_id: str,
    body: NavigateRequest,
    service: WebControlService = Depends(get_service),
) -> ActionResult:
    return await service.navigate(session_id, body)


@router.get("/content", response_model=PageContent)
async def get_page_content(
    session_id: str,
    service: WebControlService = Depends(get_service),
) -> PageContent:
    return await service.get_page_content(session_id)


@router.post("/click", response_model=ActionResult)
async def click(
    session_id: str,
    body: ClickRequest,
    service: WebControlService = Depends(get_service),
) -> ActionResult:
    return await service.click(session_id, body)


@router.post("/fill", response_model=ActionResult)
async def fill(
    session_id: str,
    body: FillRequest,
    service: WebControlService = Depends(get_service),
) -> ActionResult:
    return await service.fill(session_id, body)


@router.post("/select", response_model=ActionResult)
async def select_option(
    session_id: str,
    body: SelectRequest,
    service: WebControlService = Depends(get_service),
) -> ActionResult:
    return await service.select(session_id, body)


@router.post("/submit", response_model=ActionResult)
async def submit(
    session_id: str,
    body: SubmitRequest,
    service: WebControlService = Depends(get_service),
) -> ActionResult:
    return await service.submit(session_id, body)


@router.post("/execute-js", response_model=ActionResult)
async def execute_js(
    session_id: str,
    body: ExecuteJsRequest,
    service: WebControlService = Depends(get_service),
) -> ActionResult:
    return await service.execute_js(session_id, body)


@router.get("/screenshot", response_model=ScreenshotResult)
async def screenshot(
    session_id: str,
    service: WebControlService = Depends(get_service),
) -> ScreenshotResult:
    return await service.screenshot(session_id)
