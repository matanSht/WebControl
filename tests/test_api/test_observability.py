import pytest


@pytest.mark.asyncio
async def test_activity_empty_session(client):
    resp = await client.post("/api/v1/sessions", json={"name": "obs-test"})
    session_id = resp.json()["id"]

    resp = await client.get(f"/api/v1/sessions/{session_id}/activity")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_activity_after_navigate(client):
    resp = await client.post("/api/v1/sessions", json={"name": "obs-nav"})
    session_id = resp.json()["id"]

    await client.post(
        f"/api/v1/sessions/{session_id}/navigate",
        json={"url": "https://example.com"},
    )

    resp = await client.get(f"/api/v1/sessions/{session_id}/activity")
    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) == 1
    # The escalator tags the action with the robustness tier that handled it
    # (e.g. "navigate:direct"), so escalation is visible in the activity log.
    assert entries[0]["action"] == "navigate:direct"
    assert entries[0]["success"] is True
    assert entries[0]["url"] == "https://example.com"
    assert "duration_ms" in entries[0]
    assert entries[0]["duration_ms"] > 0


@pytest.mark.asyncio
async def test_stats_after_actions(client):
    resp = await client.post("/api/v1/sessions", json={"name": "obs-stats"})
    session_id = resp.json()["id"]

    await client.post(
        f"/api/v1/sessions/{session_id}/navigate",
        json={"url": "https://example.com"},
    )
    await client.get(f"/api/v1/sessions/{session_id}/content")

    resp = await client.get(f"/api/v1/sessions/{session_id}/stats")
    assert resp.status_code == 200
    stats = resp.json()
    assert stats["total_actions"] == 2
    assert stats["success_count"] == 2
    assert stats["error_count"] == 0
    assert stats["avg_duration_ms"] > 0


@pytest.mark.asyncio
async def test_response_headers_include_request_id(client):
    resp = await client.get("/health")
    assert "x-request-id" in resp.headers
    assert "x-response-time-ms" in resp.headers
    assert len(resp.headers["x-request-id"]) == 8


@pytest.mark.asyncio
async def test_custom_request_id_echoed(client):
    resp = await client.get("/health", headers={"x-request-id": "my-trace-42"})
    assert resp.headers["x-request-id"] == "my-trace-42"
