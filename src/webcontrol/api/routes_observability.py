import tempfile

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from webcontrol.api.dependencies import get_service
from webcontrol.core.service import WebControlService

router = APIRouter(prefix="/sessions/{session_id}", tags=["observability"])


@router.get("/activity")
async def get_session_activity(
    session_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    service: WebControlService = Depends(get_service),
) -> list[dict]:
    return await service.get_session_activity(session_id, limit)


@router.get("/stats")
async def get_session_stats(
    session_id: str,
    service: WebControlService = Depends(get_service),
) -> dict:
    return service.get_session_stats(session_id)


@router.post("/trace/export")
async def export_trace(
    session_id: str,
    service: WebControlService = Depends(get_service),
) -> FileResponse:
    path = tempfile.mktemp(suffix=".zip", prefix=f"trace-{session_id[:8]}-")
    await service.export_trace(session_id, path)
    return FileResponse(
        path=path,
        media_type="application/zip",
        filename=f"trace-{session_id[:8]}.zip",
    )
