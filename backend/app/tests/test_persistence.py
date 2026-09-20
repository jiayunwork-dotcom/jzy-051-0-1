"""Persistence tests: restore fidelity, isolation and optimistic locking."""

from __future__ import annotations

import pytest

from app.persistence import repository


@pytest.mark.asyncio
async def test_workspace_roundtrip_restores_formulas_order_and_templates(session):
    saved = await repository.create_workspace(
        session, name="论文草稿",
        formulas=[
            {"clientId": "f1", "source": r"E=mc^2 \label{energy}",
             "label": "energy"},
            {"clientId": "f2", "source": r"\ref{energy}", "label": None},
        ],
        templates=[{"name": "我的积分", "code": r"\int_{a}^{b}",
                    "category": "自定义"}])
    assert saved["version"] == 1

    loaded = await repository.get_workspace(session, saved["id"])
    assert loaded["name"] == "论文草稿"
    assert [f["clientId"] for f in loaded["formulas"]] == ["f1", "f2"]
    assert loaded["formulas"][0]["source"] == r"E=mc^2 \label{energy}"
    assert loaded["templates"][0]["name"] == "我的积分"


@pytest.mark.asyncio
async def test_reordered_formulas_persist_in_new_order(session):
    ws = await repository.create_workspace(session, formulas=[
        {"clientId": "a", "source": "1"},
        {"clientId": "b", "source": "2"},
        {"clientId": "c", "source": "3"},
    ])
    await repository.save_workspace(
        session, ws["id"], name=ws["name"], expected_version=1,
        formulas=[
            {"clientId": "c", "source": "3"},
            {"clientId": "a", "source": "1"},
            {"clientId": "b", "source": "2"},
        ])
    reloaded = await repository.get_workspace(session, ws["id"])
    assert [f["clientId"] for f in reloaded["formulas"]] == ["c", "a", "b"]
    assert [f["position"] for f in reloaded["formulas"]] == [0, 1, 2]
    assert reloaded["version"] == 2


@pytest.mark.asyncio
async def test_concurrent_saves_to_same_workspace_conflict(session):
    ws = await repository.create_workspace(session, formulas=[
        {"clientId": "a", "source": "1"}])

    # Two sessions both hold version 1 and edit differently.
    await repository.save_workspace(
        session, ws["id"], name="来自会话 A", expected_version=1,
        formulas=[{"clientId": "a", "source": "A"}])

    with pytest.raises(repository.ConcurrentModificationError) as exc:
        await repository.save_workspace(
            session, ws["id"], name="来自会话 B", expected_version=1,
            formulas=[{"clientId": "a", "source": "B"}])
    assert exc.value.current_version == 2

    # A's save won; B did not overwrite it.
    final = await repository.get_workspace(session, ws["id"])
    assert final["name"] == "来自会话 A"
    assert final["formulas"][0]["source"] == "A"


@pytest.mark.asyncio
async def test_distinct_workspaces_do_not_interfere(session):
    w1 = await repository.create_workspace(
        session, name="w1", formulas=[{"clientId": "a", "source": "1"}])
    w2 = await repository.create_workspace(
        session, name="w2", formulas=[{"clientId": "a", "source": "2"}])

    await repository.save_workspace(
        session, w1["id"], name="w1-v2", expected_version=1,
        formulas=[{"clientId": "a", "source": "11"}])
    # w2 still at version 1, untouched.
    loaded2 = await repository.get_workspace(session, w2["id"])
    assert loaded2["version"] == 1
    assert loaded2["formulas"][0]["source"] == "2"


@pytest.mark.asyncio
async def test_missing_workspace_raises(session):
    with pytest.raises(repository.WorkspaceNotFoundError):
        await repository.get_workspace(session, "does-not-exist")
