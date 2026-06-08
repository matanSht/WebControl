from datetime import datetime

from pydantic import BaseModel


class SessionCreate(BaseModel):
    name: str | None = None
    ttl_seconds: int | None = None
    viewport_width: int | None = None
    viewport_height: int | None = None
    user_agent: str | None = None
    enable_tracing: bool = False


class SessionInfo(BaseModel):
    id: str
    name: str | None
    created_at: datetime
    last_active: datetime
    ttl_seconds: int
    current_url: str | None
    is_alive: bool
