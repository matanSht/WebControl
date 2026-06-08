from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class ActivityEntry:
    timestamp: datetime
    action: str
    ref: str | None
    url: str | None
    duration_ms: float
    success: bool
    error: str | None = None

    def to_dict(self) -> dict:
        d: dict = {
            "timestamp": self.timestamp.isoformat(),
            "action": self.action,
            "duration_ms": self.duration_ms,
            "success": self.success,
        }
        if self.ref:
            d["ref"] = self.ref
        if self.url:
            d["url"] = self.url
        if self.error:
            d["error"] = self.error
        return d


@dataclass
class SessionActivityLog:
    max_entries: int = 200
    _entries: deque[ActivityEntry] = field(default_factory=lambda: deque(maxlen=200))

    def __post_init__(self) -> None:
        self._entries = deque(maxlen=self.max_entries)

    def record(
        self,
        action: str,
        duration_ms: float,
        success: bool,
        ref: str | None = None,
        url: str | None = None,
        error: str | None = None,
    ) -> None:
        self._entries.append(ActivityEntry(
            timestamp=datetime.now(UTC),
            action=action,
            ref=ref,
            url=url,
            duration_ms=duration_ms,
            success=success,
            error=error,
        ))

    def get_entries(self, limit: int = 50) -> list[dict]:
        entries = list(self._entries)[-limit:]
        return [e.to_dict() for e in entries]

    def get_stats(self) -> dict:
        if not self._entries:
            return {"total_actions": 0}

        entries = list(self._entries)
        total = len(entries)
        successes = sum(1 for e in entries if e.success)
        durations = [e.duration_ms for e in entries]

        return {
            "total_actions": total,
            "success_count": successes,
            "error_count": total - successes,
            "avg_duration_ms": round(sum(durations) / total, 2),
            "max_duration_ms": round(max(durations), 2),
            "min_duration_ms": round(min(durations), 2),
        }
