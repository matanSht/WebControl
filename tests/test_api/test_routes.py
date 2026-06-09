import pytest


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_create_and_list_sessions(client):
    resp = await client.post("/api/v1/sessions", json={"name": "test-session"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "test-session"
    assert data["is_alive"] is True
    session_id = data["id"]

    resp = await client.get("/api/v1/sessions")
    assert resp.status_code == 200
    sessions = resp.json()
    assert any(s["id"] == session_id for s in sessions)


@pytest.mark.asyncio
async def test_navigate_and_get_content(client):
    resp = await client.post("/api/v1/sessions", json={"name": "nav-test"})
    session_id = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/sessions/{session_id}/navigate",
        json={"url": "https://example.com"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "example" in data["page_content"]["title"].lower()

    resp = await client.get(f"/api/v1/sessions/{session_id}/content")
    assert resp.status_code == 200
    content = resp.json()
    assert content["url"] == "https://example.com/"


@pytest.mark.asyncio
async def test_navigate_with_settle_options(client):
    resp = await client.post("/api/v1/sessions", json={"name": "settle-test"})
    session_id = resp.json()["id"]

    # wait_for_selector + scroll_to_load exercise the settle path before parse.
    resp = await client.post(
        f"/api/v1/sessions/{session_id}/navigate",
        json={
            "url": "https://example.com",
            "wait_for_selector": "h1",
            "scroll_to_load": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "example" in data["page_content"]["title"].lower()


@pytest.mark.asyncio
async def test_close_session(client):
    resp = await client.post("/api/v1/sessions", json={})
    session_id = resp.json()["id"]

    resp = await client.delete(f"/api/v1/sessions/{session_id}")
    assert resp.status_code == 204

    resp = await client.get(f"/api/v1/sessions/{session_id}/content")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_session_not_found(client):
    resp = await client.get("/api/v1/sessions/nonexistent/content")
    assert resp.status_code == 404
