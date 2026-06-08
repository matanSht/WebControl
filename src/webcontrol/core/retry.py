import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

from playwright.async_api import Error as PlaywrightError

logger = logging.getLogger("webcontrol.retry")

T = TypeVar("T")


async def with_retry(
    fn: Callable[[], Coroutine[Any, Any, T]],
    retries: int,
    delay_ms: int,
    operation: str = "operation",
) -> T:
    last_error: Exception | None = None
    for attempt in range(1 + retries):
        try:
            return await fn()
        except PlaywrightError as e:
            last_error = e
            if attempt < retries:
                logger.warning(
                    "%s failed (attempt %d/%d): %s — retrying in %dms",
                    operation,
                    attempt + 1,
                    1 + retries,
                    str(e)[:200],
                    delay_ms,
                )
                await asyncio.sleep(delay_ms / 1000)
            else:
                logger.error(
                    "%s failed after %d attempts: %s",
                    operation,
                    1 + retries,
                    str(e)[:200],
                )
    raise last_error  # type: ignore[misc]
