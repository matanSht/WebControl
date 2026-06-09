import pytest


async def _new_session(client) -> str:
    resp = await client.post("/api/v1/sessions", json={})
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_capture_records_navigation_response(client):
    session_id = await _new_session(client)

    # The example.com document is text/html, so json_only must be false to keep it.
    resp = await client.post(
        f"/api/v1/sessions/{session_id}/network-capture",
        json={"enabled": True, "json_only": False, "url_filter": "example.com"},
    )
    assert resp.status_code == 200
    assert resp.json()["enabled"] is True

    resp = await client.post(
        f"/api/v1/sessions/{session_id}/navigate", json={"url": "https://example.com"}
    )
    assert resp.status_code == 200

    resp = await client.get(f"/api/v1/sessions/{session_id}/network-capture")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 1
    doc = next(
        (
            r
            for r in data["responses"]
            if isinstance(r["body"], str) and "Example Domain" in r["body"]
        ),
        None,
    )
    assert doc is not None
    assert doc["status"] == 200
    assert "example.com" in doc["url"]


@pytest.mark.asyncio
async def test_capture_disabled_records_nothing(client):
    session_id = await _new_session(client)

    resp = await client.post(
        f"/api/v1/sessions/{session_id}/navigate", json={"url": "https://example.com"}
    )
    assert resp.status_code == 200

    resp = await client.get(f"/api/v1/sessions/{session_id}/network-capture")
    assert resp.json()["count"] == 0


@pytest.mark.asyncio
async def test_capture_stop_and_clear(client):
    session_id = await _new_session(client)
    await client.post(
        f"/api/v1/sessions/{session_id}/network-capture",
        json={"enabled": True, "json_only": False, "url_filter": "example.com"},
    )
    await client.post(
        f"/api/v1/sessions/{session_id}/navigate", json={"url": "https://example.com"}
    )

    resp = await client.post(
        f"/api/v1/sessions/{session_id}/network-capture", json={"enabled": False}
    )
    assert resp.json()["enabled"] is False

    resp = await client.delete(f"/api/v1/sessions/{session_id}/network-capture")
    assert resp.status_code == 204

    resp = await client.get(f"/api/v1/sessions/{session_id}/network-capture")
    assert resp.json()["count"] == 0
