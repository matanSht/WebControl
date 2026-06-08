import contextvars
import uuid

_request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


def get_request_id() -> str:
    return _request_id_var.get()


def set_request_id(request_id: str | None = None) -> str:
    rid = request_id or str(uuid.uuid4())[:8]
    _request_id_var.set(rid)
    return rid
