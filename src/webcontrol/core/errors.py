class WebControlError(Exception):
    pass


class SessionNotFoundError(WebControlError):
    def __init__(self, session_id: str):
        super().__init__(f"Session not found: {session_id}")
        self.session_id = session_id


class MaxSessionsError(WebControlError):
    def __init__(self, max_sessions: int):
        super().__init__(f"Maximum sessions reached: {max_sessions}")
        self.max_sessions = max_sessions


class ElementNotFoundError(WebControlError):
    def __init__(self, ref: str):
        super().__init__(
            f"Element ref '{ref}' not found. Page may have changed — call get_page_content() to refresh."
        )
        self.ref = ref


class NavigationError(WebControlError):
    pass


class ActionError(WebControlError):
    pass


class SearchError(WebControlError):
    pass


class SearchNotConfiguredError(WebControlError):
    def __init__(self) -> None:
        super().__init__(
            "Search tier is not configured. Set WC_SEARCH_TIER_ENABLED=true and WC_SEARCH_API_KEY."
        )
