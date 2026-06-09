import pytest


async def _new_session(client) -> str:
    resp = await client.post("/api/v1/sessions", json={})
    return resp.json()["id"]


async def _navigate(client, session_id: str, url: str = "https://example.com") -> None:
    resp = await client.post(f"/api/v1/sessions/{session_id}/navigate", json={"url": url})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_extract_rows_text_and_attribute(client):
    session_id = await _new_session(client)
    await _navigate(client, session_id)

    resp = await client.post(
        f"/api/v1/sessions/{session_id}/extract",
        json={
            "selector": "a",
            "fields": [
                {"name": "text"},
                {"name": "href", "attribute": "href"},
            ],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["count"] >= 1
    first = data["rows"][0]
    assert first["text"]
    assert first["href"].startswith("http")


@pytest.mark.asyncio
async def test_extract_missing_target_is_null(client):
    session_id = await _new_session(client)
    await _navigate(client, session_id)

    # example.com's link has no <img> child — the field must come back null,
    # not error.
    resp = await client.post(
        f"/api/v1/sessions/{session_id}/extract",
        json={
            "selector": "a",
            "fields": [{"name": "img", "selector": "img", "attribute": "src"}],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["rows"][0]["img"] is None


@pytest.mark.asyncio
async def test_extract_no_match_returns_empty(client):
    session_id = await _new_session(client)
    await _navigate(client, session_id)

    resp = await client.post(
        f"/api/v1/sessions/{session_id}/extract",
        json={"selector": ".definitely-not-on-this-page", "fields": [{"name": "x"}]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["count"] == 0
    assert data["rows"] == []


@pytest.mark.asyncio
async def test_structured_data_captures_json_ld(client):
    session_id = await _new_session(client)
    await _navigate(client, session_id)

    # Inject a JSON-LD Product blob, then let the re-parse pick it up.
    script = (
        "(() => {"
        "  const s = document.createElement('script');"
        "  s.type = 'application/ld+json';"
        "  s.textContent = JSON.stringify({"
        "    '@type': 'Product', name: 'Widget',"
        "    offers: { '@type': 'Offer', price: '12.99', priceCurrency: 'USD' }"
        "  });"
        "  document.head.appendChild(s);"
        "})()"
    )
    resp = await client.post(f"/api/v1/sessions/{session_id}/execute-js", json={"script": script})
    assert resp.status_code == 200
    structured = resp.json()["page_content"]["structured_data"]
    assert any(
        blob.get("@type") == "Product" and blob["offers"]["price"] == "12.99" for blob in structured
    )


@pytest.mark.asyncio
async def test_get_html(client):
    session_id = await _new_session(client)
    await _navigate(client, session_id)

    resp = await client.get(f"/api/v1/sessions/{session_id}/html")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "<html" in data["html"].lower()
    assert "example domain" in data["html"].lower()
    assert data["truncated"] is False


@pytest.mark.asyncio
async def test_get_accessibility_tree(client):
    session_id = await _new_session(client)
    await _navigate(client, session_id)

    resp = await client.get(f"/api/v1/sessions/{session_id}/accessibility")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["snapshot"]
    # ARIA snapshot YAML lists the page's semantic structure.
    assert "Example Domain" in data["snapshot"]
