"""PostgreSQL 持久化层。

设计要点：
- 工作区与其公式整体作为一个文档保存（JSONB 存储公式列表，保证公式顺序、
  标签、自定义模板随工作区原子落库）；
- 每个工作区带单调递增的 version 与 updated_at；保存时必须带“我读过的
  version”，UPDATE 用 WHERE version = :expected 做乐观锁：
  * 更新命中 → 返回新版本；
  * 未命中（已被别人先保存）→ 抛 :class:`ConcurrentUpdateError`，
    由 API 转成 409，绝不发生后写覆盖先写的串写。
"""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import asyncpg

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://latex:latex@db:5432/latex_editor",
)


class ConcurrentUpdateError(Exception):
    def __init__(self, workspace_id: str, expected: int, actual: int):
        super().__init__(
            f"工作区 {workspace_id} 已被其他会话修改"
            f"（期望版本 {expected}，当前版本 {actual}），请刷新后合并再保存")
        self.workspace_id = workspace_id
        self.expected = expected
        self.actual = actual


class WorkspaceNotFoundError(Exception):
    pass


@dataclass
class Workspace:
    id: str
    name: str
    version: int
    formulas: list[dict]
    templates: list[dict]
    created_at: datetime
    updated_at: datetime

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "formulas": self.formulas,
            "templates": self.templates,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


async def _pool() -> asyncpg.Pool:
    if getattr(_pool, "_pool", None) is None:
        _pool._pool = await asyncpg.create_pool(
            DATABASE_URL, min_size=1, max_size=10, timeout=30)
    return _pool._pool


async def init_db() -> None:
    pool = await _pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workspaces (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                version     INTEGER NOT NULL DEFAULT 1,
                formulas    JSONB NOT NULL DEFAULT '[]'::jsonb,
                templates   JSONB NOT NULL DEFAULT '[]'::jsonb,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            """
        )


async def close_db() -> None:
    pool = getattr(_pool, "_pool", None)
    if pool is not None:
        await pool.close()
        _pool._pool = None


def _row_to_workspace(row: asyncpg.Record) -> Workspace:
    return Workspace(
        id=row["id"],
        name=row["name"],
        version=row["version"],
        formulas=json.loads(row["formulas"]),
        templates=json.loads(row["templates"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def list_workspaces() -> list[dict]:
    pool = await _pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name, version, updated_at "
            "FROM workspaces ORDER BY updated_at DESC")
    return [{"id": r["id"], "name": r["name"], "version": r["version"],
             "updated_at": r["updated_at"].isoformat()} for r in rows]


async def get_workspace(workspace_id: str) -> Workspace:
    pool = await _pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM workspaces WHERE id = $1", workspace_id)
    if row is None:
        raise WorkspaceNotFoundError(workspace_id)
    return _row_to_workspace(row)


async def create_workspace(name: str, formulas: list[dict] | None = None,
                           templates: list[dict] | None = None) -> Workspace:
    workspace_id = uuid.uuid4().hex
    pool = await _pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO workspaces (id, name, version, formulas, templates)
            VALUES ($1, $2, 1, $3::jsonb, $4::jsonb)
            RETURNING *
            """,
            workspace_id, name,
            json.dumps(formulas or [], ensure_ascii=False),
            json.dumps(templates or [], ensure_ascii=False),
        )
    return _row_to_workspace(row)


async def save_workspace(workspace_id: str, name: str, formulas: list[dict],
                         templates: list[dict], expected_version: int) -> Workspace:
    """按乐观锁条件整体保存。版本不匹配抛 :class:`ConcurrentUpdateError`。"""
    pool = await _pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT version FROM workspaces WHERE id = $1 FOR UPDATE",
                workspace_id)
            if row is None:
                raise WorkspaceNotFoundError(workspace_id)
            actual = row["version"]
            if actual != expected_version:
                raise ConcurrentUpdateError(workspace_id,
                                            expected_version, actual)
            updated = await conn.fetchrow(
                """
                UPDATE workspaces
                SET name = $2,
                    formulas = $3::jsonb,
                    templates = $4::jsonb,
                    version = version + 1,
                    updated_at = now()
                WHERE id = $1 AND version = $5
                RETURNING *
                """,
                workspace_id, name,
                json.dumps(formulas, ensure_ascii=False),
                json.dumps(templates, ensure_ascii=False),
                expected_version,
            )
    return _row_to_workspace(updated)


async def delete_workspace(workspace_id: str) -> bool:
    pool = await _pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM workspaces WHERE id = $1",
                                    workspace_id)
    return result.endswith("1")
