"""End-to-end HTTP tests against the FastAPI ASGI app (no network)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


@pytest.fixture()
async def client():
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.api.routes import get_session
    from app.main import app
    from app.persistence.models import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def _override():
        async with maker() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        yield c
    app.dependency_overrides.clear()
    await engine.dispose()


async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_render_endpoint_strict_and_tolerant(client):
    r = await client.post("/api/render",
                          json={"source": r"\alpha+\beta", "tolerant": False})
    body = r.json()
    assert body["ok"] is True
    assert "α" in body["mathml"] and "β" in body["mathml"]

    r = await client.post("/api/render",
                          json={"source": r"\bogus", "tolerant": True})
    body = r.json()
    assert body["ok"] is False
    assert body["mathml"] and "latex-error" in body["mathml"]


async def test_parse_endpoint_reports_spelling(client):
    r = await client.post("/api/parse", json={"source": r"\alhpa"})
    err = r.json()["errors"][0]
    assert err["code"] == "unknown_command"
    assert err["suggestion"] == r"\alpha"


async def test_preview_endpoint_numbers_and_refs(client):
    r = await client.post("/api/preview", json={"formulas": [
        {"clientId": "a", "source": r"\label{e}E=mc^2"},
        {"clientId": "b", "source": r"(\ref{e})"},
    ]})
    body = r.json()
    assert body["ok"] is True
    by_id = {f["clientId"]: f for f in body["formulas"]}
    assert by_id["a"]["number"] == 1 and by_id["b"]["number"] == 2
    assert '>1</mi>' in by_id["b"]["mathml"]


async def test_preview_flags_undefined_and_cycle(client):
    r = await client.post("/api/preview", json={"formulas": [
        {"clientId": "a", "source": r"\ref{missing}"},
    ]})
    assert r.json()["issues"][0]["code"] == "undefined_label"

    r = await client.post("/api/preview", json={"formulas": [
        {"clientId": "a", "source": r"\label{a}\ref{b}"},
        {"clientId": "b", "source": r"\label{b}\ref{a}"},
    ]})
    codes = {i["code"] for i in r.json()["issues"]}
    assert codes == {"reference_cycle"}


async def test_workspace_crud_and_conflict(client):
    r = await client.post("/api/workspaces", json={
        "name": "ws",
        "formulas": [{"clientId": "f1", "source": "x"}]})
    assert r.status_code == 201
    ws = r.json()
    wid, version = ws["id"], ws["version"]

    r = await client.get(f"/api/workspaces/{wid}")
    assert r.json()["formulas"][0]["source"] == "x"

    # First save with correct version succeeds.
    r = await client.put(f"/api/workspaces/{wid}", json={
        "name": "ws2", "expectedVersion": version,
        "formulas": [{"clientId": "f1", "source": "y"}]})
    assert r.status_code == 200 and r.json()["version"] == 2

    # Stale version is rejected with 409, not an overwrite.
    r = await client.put(f"/api/workspaces/{wid}", json={
        "name": "ws3", "expectedVersion": 1,
        "formulas": [{"clientId": "f1", "source": "z"}]})
    assert r.status_code == 409
    assert r.json()["detail"]["currentVersion"] == 2

    r = await client.get(f"/api/workspaces/{wid}")
    assert r.json()["name"] == "ws2"


async def test_palette_exposes_categories(client):
    r = await client.get("/api/palette")
    keys = {c["key"] for c in r.json()["categories"]}
    assert {"greek", "operators", "relations", "arrows"} <= keys


async def test_404_for_unknown_workspace(client):
    r = await client.get("/api/workspaces/nope")
    assert r.status_code == 404
