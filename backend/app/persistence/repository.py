"""Workspace persistence repository.

All multi-row mutations happen inside one transaction so saving a workspace
is atomic.  Optimistic locking (the ``expected_version`` field) guarantees
that two concurrent saves of the *same* workspace cannot silently overwrite
one another, while saves of *different* workspaces proceed independently.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import CustomTemplate, Formula, Workspace


class WorkspaceNotFoundError(LookupError):
    pass


class ConcurrentModificationError(RuntimeError):
    def __init__(self, workspace_id: str, current_version: int):
        super().__init__(
            f"工作区 {workspace_id} 已被其他会话修改"
            f"（当前版本 {current_version}），请刷新后再保存。")
        self.workspace_id = workspace_id
        self.current_version = current_version


async def create_workspace(session: AsyncSession, *, name: str = "未命名工作区",
                           formulas: list[dict] | None = None,
                           templates: list[dict] | None = None) -> dict:
    # Attach children BEFORE flush: assigning a collection on a transient
    # object never triggers lazy IO (doing it after flush would).
    ws = Workspace(name=name)
    _replace_formulas(ws, formulas or [])
    _replace_templates(ws, templates or [])
    session.add(ws)
    await session.commit()
    return _serialize(ws)


async def get_workspace(session: AsyncSession, workspace_id: str) -> dict:
    ws = await _load(session, workspace_id)
    return _serialize(ws)


async def list_workspaces(session: AsyncSession) -> list[dict]:
    result = await session.execute(
        select(Workspace).order_by(Workspace.updated_at.desc()))
    return [_serialize(ws) for ws in result.scalars().all()]


async def save_workspace(session: AsyncSession, workspace_id: str, *,
                         name: str, expected_version: int,
                         formulas: list[dict],
                         templates: list[dict] | None = None) -> dict:
    ws = await _load(session, workspace_id, lock=True)
    if ws.version != expected_version:
        raise ConcurrentModificationError(workspace_id, ws.version)

    ws.name = name
    ws.version += 1
    ws.updated_at = datetime.now(timezone.utc)
    _replace_formulas(ws, formulas)
    _replace_templates(ws, templates or [])
    await session.commit()
    return _serialize(ws)


async def delete_workspace(session: AsyncSession, workspace_id: str) -> None:
    ws = await _load(session, workspace_id)
    await session.delete(ws)
    await session.commit()


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


async def _load(session: AsyncSession, workspace_id: str, *,
                lock: bool = False) -> Workspace:
    stmt = select(Workspace).where(Workspace.id == workspace_id).options(
        selectinload(Workspace.formulas),
        selectinload(Workspace.templates))
    if lock:
        stmt = stmt.with_for_update()
    result = await session.execute(stmt)
    ws = result.scalar_one_or_none()
    if ws is None:
        raise WorkspaceNotFoundError(workspace_id)
    return ws


def _replace_formulas(ws: Workspace, formulas: list[dict]) -> None:
    # mutate in place so SQLAlchemy emits DELETEs for the orphans before
    # INSERTs (a wholesale ws.formulas = [...] assignment bypasses that).
    ws.formulas.clear()
    for i, f in enumerate(formulas):
        ws.formulas.append(Formula(
            client_id=f.get("clientId", f"f{i}"),
            source=f.get("source", ""),
            label=(f.get("label") or None),
            position=i))


def _replace_templates(ws: Workspace, templates: list[dict]) -> None:
    ws.templates.clear()
    for i, t in enumerate(templates):
        ws.templates.append(CustomTemplate(
            name=t.get("name", "模板"), code=t.get("code", ""),
            category=t.get("category", "自定义"), position=i))


def _serialize(ws: Workspace) -> dict:
    # Collections are built/loaded in position order; iterate them
    # directly (sorted() can trigger a lazy refresh after commit).
    formulas = sorted(ws.__dict__.get("formulas", []),
                      key=lambda f: f.position)
    templates = sorted(ws.__dict__.get("templates", []),
                       key=lambda t: t.position)
    return {
        "id": ws.id,
        "name": ws.name,
        "version": ws.version,
        "createdAt": ws.created_at.isoformat() if ws.created_at else None,
        "updatedAt": ws.updated_at.isoformat() if ws.updated_at else None,
        "formulas": [
            {"clientId": f.client_id, "source": f.source,
             "label": f.label, "position": f.position}
            for f in formulas
        ],
        "templates": [
            {"name": t.name, "code": t.code, "category": t.category,
             "position": t.position}
            for t in templates
        ],
    }
