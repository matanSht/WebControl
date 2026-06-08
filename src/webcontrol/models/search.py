from datetime import datetime

from pydantic import BaseModel


class SearchRequest(BaseModel):
    query: str
    max_results: int | None = None
    fetch_contents: bool | None = None


class SearchResultItem(BaseModel):
    title: str
    url: str
    snippet: str = ""
    content: str = ""
    published_date: str = ""
    score: float | None = None


class SearchResult(BaseModel):
    success: bool
    query: str
    provider: str
    tier_used: str = "search"
    results: list[SearchResultItem] = []
    error: str | None = None
    timestamp: datetime
