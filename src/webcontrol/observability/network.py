"""Per-session capture of XHR/fetch responses.

The deepest accuracy lever: instead of scraping JS-rendered values out of the
DOM, record the raw API payloads a page's frontend fetches. The price/listing
data behind an Amazon search page (or any SPA) usually arrives as JSON over
fetch/XHR — capturing those responses gives the agent the source data directly.

A ``NetworkCapture`` is a bounded ring buffer that is **disabled by default**.
When enabled, a ``page.on("response")`` listener (wired up in
``core/session_manager.py``) records responses matching the filters — JSON
content-type by default, optionally narrowed to a URL substring. Bodies are
read on a background task; ``drain()`` lets a reader wait for in-flight reads to
finish before snapshotting the buffer.
"""

import asyncio
import json
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class CapturedResponse:
    timestamp: datetime
    url: str
    status: int
    method: str
    resource_type: str
    content_type: str
    body: Any  # parsed JSON, or text (size-capped) when not JSON / too large

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "url": self.url,
            "status": self.status,
            "method": self.method,
            "resource_type": self.resource_type,
            "content_type": self.content_type,
            "body": self.body,
        }


def parse_body(text: str, content_type: str, max_body_chars: int) -> Any:
    """Parse a response body to JSON when possible, else return capped text.

    Large bodies are returned as truncated text (never parsed) so a single huge
    response cannot blow up memory.
    """
    if len(text) > max_body_chars:
        return text[:max_body_chars]
    if "json" in content_type.lower():
        try:
            return json.loads(text)
        except ValueError:
            return text
    return text


@dataclass
class NetworkCapture:
    max_entries: int = 50
    max_body_chars: int = 100_000
    enabled: bool = False
    url_filter: str | None = None
    json_only: bool = True
    _entries: deque = field(default_factory=deque, repr=False)
    _pending: set = field(default_factory=set, repr=False)

    def __post_init__(self) -> None:
        self._entries = deque(maxlen=self.max_entries)

    def configure(
        self, *, enabled: bool, url_filter: str | None = None, json_only: bool = True
    ) -> None:
        self.enabled = enabled
        self.url_filter = url_filter
        self.json_only = json_only

    def matches(self, url: str, resource_type: str, content_type: str) -> bool:
        """Cheap synchronous filter, applied before a body-read task is spawned."""
        if not self.enabled:
            return False
        if self.json_only and "json" not in content_type.lower():
            return False
        if self.url_filter and self.url_filter not in url:
            return False
        return True

    def track(self, task: asyncio.Task) -> None:
        """Hold a reference to an in-flight body-read task (and auto-discard it)."""
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    async def drain(self, timeout: float = 2.0) -> None:
        """Wait for in-flight body reads so a reader sees a complete snapshot."""
        if self._pending:
            await asyncio.wait(set(self._pending), timeout=timeout)

    def record(self, captured: CapturedResponse) -> None:
        self._entries.append(captured)

    def get_entries(self, limit: int = 50, url_filter: str | None = None) -> list[dict]:
        entries = list(self._entries)
        if url_filter:
            entries = [e for e in entries if url_filter in e.url]
        return [e.to_dict() for e in entries[-limit:]]

    def clear(self) -> None:
        self._entries.clear()
