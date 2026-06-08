import time


class Timer:
    def __init__(self) -> None:
        self._start: float = 0
        self._elapsed_ms: float = 0

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_) -> None:
        self._elapsed_ms = (time.perf_counter() - self._start) * 1000

    @property
    def elapsed_ms(self) -> float:
        if self._elapsed_ms:
            return round(self._elapsed_ms, 2)
        return round((time.perf_counter() - self._start) * 1000, 2)
