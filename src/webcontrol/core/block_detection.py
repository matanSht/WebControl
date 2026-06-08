"""Detect anti-bot block pages that return without an HTTP error.

The hard problem this solves: a bot wall (Amazon/PerimeterX, Cloudflare,
DataDome, Akamai) usually serves its challenge with **HTTP 200** and a normal
DOM, so ``page.goto()`` never raises. Naive automation then treats the block
page as a successful navigation. This module inspects the response status and
the parsed page text to recognize those blocks so callers can escalate instead
of reporting false success.

``detect_block`` is a pure function (no I/O, no side effects) — easy to unit
test and cheap to call after every navigation attempt.
"""

from webcontrol.models.page import PageContent

# Statuses that, on a top-level navigation, almost always mean "blocked /
# rate-limited" rather than a genuine application response.
BLOCK_STATUSES = frozenset({403, 429, 503})

# Substrings (matched case-insensitively against title + visible text) that
# strongly indicate a challenge or block interstitial rather than real content.
BLOCK_MARKERS: tuple[str, ...] = (
    "robot check",
    "something went wrong",  # Amazon's generic block interstitial
    "enter the characters you see",  # Amazon CAPTCHA
    "type the characters you see",
    "are you a human",
    "are you a robot",
    "unusual traffic",  # Google
    "automated access",
    "to discuss automated access",  # Amazon
    "access denied",  # Akamai / generic
    "access to this page has been denied",
    "checking your browser",  # Cloudflare interstitial
    "verify you are a human",
    "verifying you are human",
    "px-captcha",  # PerimeterX
    "captcha",
    "cf-challenge",  # Cloudflare
    "blocked",
)

# Below this many characters of visible text, with zero interactive elements,
# we treat a page bearing a suspicious title as an empty challenge shell.
_EMPTY_TEXT_THRESHOLD = 64


def detect_block(status: int | None, content: PageContent) -> str | None:
    """Return a human-readable reason if the page looks like a bot block, else None.

    Args:
        status: HTTP status of the top-level navigation response, or None if
            Playwright returned no response (e.g. same-document navigation).
        content: The parsed page content for the loaded document.
    """
    if status is not None and status in BLOCK_STATUSES:
        return f"HTTP {status} on navigation (likely blocked or rate-limited)"

    haystack = f"{content.title}\n{content.text_content}".lower()
    for marker in BLOCK_MARKERS:
        if marker in haystack:
            return f"block marker matched: {marker!r}"

    # Empty/near-empty challenge shell: no interactive elements, almost no text,
    # but a title that isn't an ordinary page title.
    stripped = content.text_content.strip()
    if not content.elements and len(stripped) < _EMPTY_TEXT_THRESHOLD:
        title_l = content.title.lower()
        if not title_l or any(m in title_l for m in ("just a moment", "attention required", "error")):
            return "empty challenge shell (no interactive elements, minimal text)"

    return None
