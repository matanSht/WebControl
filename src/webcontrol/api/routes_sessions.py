from fastapi import APIRouter, Depends

from webcontrol.api.dependencies import get_service
from webcontrol.core.service import WebControlService
from webcontrol.models.session import SessionCreate, SessionInfo

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionInfo, status_code=201)
async def create_session(
    body: SessionCreate,
    service: WebControlService = Depends(get_service),
) -> SessionInfo:
    return await service.create_session(body)


@router.get("", response_model=list[SessionInfo])
async def list_sessions(
    service: WebControlService = Depends(get_service),
) -> list[SessionInfo]:
    return service.list_sessions()


@router.delete("/{session_id}", status_code=204)
async def close_session(
    session_id: str,
    service: WebControlService = Depends(get_service),
) -> None:
    await service.close_session(session_id)
