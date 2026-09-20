"""工作区持久化与乐观锁测试。

需要可连接的 PostgreSQL；环境不可达时自动跳过（docker compose 环境会执行）。
可用 DATABASE_URL 覆盖连接串。
"""
from __future__ import annotations

import pytest

pytest.importorskip("asyncpg")

from app.db import repository  # noqa: E402


async def _db_available() -> bool:
    try:
        await repository.init_db()
        return True
    except Exception:
        return False


@pytest.fixture()
async def pool_ready():
    if not await _db_available():
        pytest.skip("PostgreSQL 不可达")
    yield
    await repository.close_db()


@pytest.mark.asyncio
async def test_create_get_and_restore_roundtrip(pool_ready):
    ws = await repository.create_workspace(
        "t1",
        formulas=[{"id": "f1", "source": r"x=y \label{a}", "label": None}],
        templates=[{"name": "自定义", "code": r"\custom{#1}"}],
    )
    try:
        assert ws.version == 1
        fetched = await repository.get_workspace(ws.id)
        assert fetched.formulas == ws.formulas
        assert fetched.templates == ws.templates
        assert fetched.name == "t1"
    finally:
        await repository.delete_workspace(ws.id)


@pytest.mark.asyncio
async def test_optimistic_lock_rejects_stale_writes(pool_ready):
    ws = await repository.create_workspace("t2")
    try:
        # 第一次保存成功，版本涨到 2
        saved = await repository.save_workspace(
            ws.id, "t2", [{"id": "a", "source": "1", "label": None}], [], 1)
        assert saved.version == 2
        # 另一个会话仍拿着旧版本 1 保存，必须被拒绝而不是覆盖
        with pytest.raises(repository.ConcurrentUpdateError) as ei:
            await repository.save_workspace(
                ws.id, "t2-stale",
                [{"id": "a", "source": "STALE", "label": None}], [], 1)
        assert ei.value.actual == 2 and ei.value.expected == 1
        # 先写者的数据原样保留
        again = await repository.get_workspace(ws.id)
        assert again.formulas[0]["source"] == "1"
        assert again.name == "t2"
        # 拿新版本再保存则成功
        saved2 = await repository.save_workspace(
            ws.id, "t3",
            [{"id": "a", "source": "2", "label": None}], [], 2)
        assert saved2.version == 3
    finally:
        await repository.delete_workspace(ws.id)


@pytest.mark.asyncio
async def test_concurrent_workspaces_do_not_cross_write(pool_ready):
    w1 = await repository.create_workspace("w1")
    w2 = await repository.create_workspace("w2")
    try:
        await repository.save_workspace(
            w1.id, "w1", [{"id": "a", "source": "AAA", "label": None}],
            [], 1)
        await repository.save_workspace(
            w2.id, "w2", [{"id": "a", "source": "BBB", "label": None}],
            [], 1)
        r1 = await repository.get_workspace(w1.id)
        r2 = await repository.get_workspace(w2.id)
        assert r1.formulas[0]["source"] == "AAA"
        assert r2.formulas[0]["source"] == "BBB"
    finally:
        await repository.delete_workspace(w1.id)
        await repository.delete_workspace(w2.id)
