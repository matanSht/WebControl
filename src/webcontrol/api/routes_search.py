from fastapi import APIRouter, Depends

from webcontrol.api.dependencies import get_service
from webcontrol.core.service import WebControlService
from webcontrol.models.search import SearchRequest, SearchResult

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResult)
async def search(
    body: SearchRequest,
    service: WebControlService = Depends(get_service),
) -> SearchResult:
    return await service.search(body)
