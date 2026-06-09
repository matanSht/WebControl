from datetime import UTC, datetime

from webcontrol.observability.network import CapturedResponse, NetworkCapture, parse_body


def _cap(url: str, body="{}") -> CapturedResponse:
    return CapturedResponse(
        timestamp=datetime.now(UTC),
        url=url,
        status=200,
        method="GET",
        resource_type="fetch",
        content_type="application/json",
        body=body,
    )


def test_disabled_does_not_match():
    nc = NetworkCapture()
    assert nc.matches("https://x/api", "fetch", "application/json") is False


def test_json_only_filters_non_json():
    nc = NetworkCapture()
    nc.configure(enabled=True, json_only=True)
    assert nc.matches("https://x/api", "fetch", "application/json") is True
    assert nc.matches("https://x/page", "document", "text/html") is False


def test_json_only_false_matches_any_content_type():
    nc = NetworkCapture()
    nc.configure(enabled=True, json_only=False)
    assert nc.matches("https://x/page", "document", "text/html") is True


def test_url_filter_narrows_matches():
    nc = NetworkCapture()
    nc.configure(enabled=True, url_filter="/api/", json_only=False)
    assert nc.matches("https://x/api/price", "fetch", "application/json") is True
    assert nc.matches("https://x/static.js", "script", "text/javascript") is False


def test_ring_buffer_caps_entries():
    nc = NetworkCapture(max_entries=2)
    for i in range(5):
        nc.record(_cap(f"https://x/{i}"))
    entries = nc.get_entries()
    assert len(entries) == 2
    assert entries[-1]["url"] == "https://x/4"


def test_get_entries_url_filter_and_limit():
    nc = NetworkCapture()
    nc.record(_cap("https://a/api"))
    nc.record(_cap("https://b/page"))
    nc.record(_cap("https://a/api2"))
    assert [e["url"] for e in nc.get_entries(url_filter="a/api")] == [
        "https://a/api",
        "https://a/api2",
    ]
    assert len(nc.get_entries(limit=1)) == 1


def test_clear_empties_buffer():
    nc = NetworkCapture()
    nc.record(_cap("https://x/1"))
    nc.clear()
    assert nc.get_entries() == []


def test_parse_body_parses_json():
    assert parse_body('{"a": 1}', "application/json", 1000) == {"a": 1}


def test_parse_body_falls_back_to_text_on_invalid_json():
    assert parse_body("not json", "application/json", 1000) == "not json"


def test_parse_body_truncates_oversized_body():
    assert parse_body("x" * 50, "application/json", 10) == "x" * 10


def test_parse_body_returns_non_json_as_text():
    assert parse_body("<html>", "text/html", 1000) == "<html>"
