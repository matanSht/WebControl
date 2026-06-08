import json
import logging
import sys
from datetime import UTC, datetime

from webcontrol.config import Settings
from webcontrol.observability.context import get_request_id


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = get_request_id()
        if request_id:
            log_entry["request_id"] = request_id
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)
        extra = {k: v for k, v in record.__dict__.items() if k.startswith("ctx_")}
        if extra:
            log_entry["context"] = {k.removeprefix("ctx_"): v for k, v in extra.items()}
        return json.dumps(log_entry)


class HumanFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        request_id = get_request_id()
        rid_part = f" [{request_id}]" if request_id else ""
        base = f"%(asctime)s %(levelname)-8s [%(name)s]{rid_part} %(message)s"
        formatter = logging.Formatter(base, datefmt="%H:%M:%S")
        return formatter.format(record)


def setup_logging(settings: Settings) -> None:
    root = logging.getLogger("webcontrol")
    root.setLevel(settings.log_level.upper())

    handler = logging.StreamHandler(sys.stdout)
    if settings.log_json:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(HumanFormatter())

    root.handlers = [handler]
    root.propagate = False
