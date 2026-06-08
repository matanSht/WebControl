from fastapi import Request

from webcontrol.core.service import WebControlService


def get_service(request: Request) -> WebControlService:
    return request.app.state.service
