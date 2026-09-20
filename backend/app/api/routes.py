"""HTTP routes.

* ``/api/parse``   — strict/tolerant lexing + structural parse, errors only;
* ``/api/render``  — parse plus MathML for one formula;
* ``/api/preview`` — workspace-wide numbering, cross references and render;
* ``/api/workspaces`` — persistence (CRUD with optimistic locking);
* ``/api/palette``    — symbol catalogue backing the frontend panels.

Everything formula-related is computed in the backend; the responses are
the exact dict contracts produced by :mod:`app.core.service`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..core import commands, service
from ..persistence import repository
from ..persistence.db import get_session
from .schemas import (
    CreateWorkspaceIn,
    ParseIn,
    PreviewIn,
    RenderIn,
    SaveWorkspaceIn,
)

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Formula kernel endpoints
# ---------------------------------------------------------------------------


@router.post("/parse")
async def parse_formula(payload: ParseIn) -> dict:
    return service.parse_formula(payload.source)


@router.post("/render")
async def render_formula(payload: RenderIn) -> dict:
    return service.render_formula(payload.source,
                                  tolerant=payload.tolerant, refs=payload.refs)


@router.post("/preview")
async def preview(payload: PreviewIn) -> dict:
    return service.preview_workspace(
        [f.model_dump() for f in payload.formulas],
        tolerant=payload.tolerant)


# ---------------------------------------------------------------------------
# Symbol palette (same command catalogue used by the parser)
# ---------------------------------------------------------------------------


@router.get("/palette")
async def palette() -> dict:
    def items(table: dict[str, str]) -> list[dict]:
        return [{"command": k, "symbol": v} for k, v in table.items()]

    return {
        "categories": [
            {"key": "greek", "label": "希腊字母",
             "items": items(commands.GREEK)},
            {"key": "operators", "label": "运算符",
             "items": items({**commands.BINARY_OPERATORS,
                             **commands.BIG_OPERATORS})},
            {"key": "relations", "label": "关系符号",
             "items": items(commands.RELATIONS)},
            {"key": "arrows", "label": "箭头",
             "items": items(commands.ARROWS)},
            {"key": "dots", "label": "点与杂项",
             "items": items({**commands.DOTS, **commands.MISC_SYMBOLS})},
            {"key": "delimiters", "label": "括号/定界符",
             "items": items(commands.DELIMITERS)},
        ]
    }


# ---------------------------------------------------------------------------
# Workspace persistence
# ---------------------------------------------------------------------------


@router.get("/workspaces")
async def list_workspaces(
        session: AsyncSession = Depends(get_session)) -> list[dict]:
    return await repository.list_workspaces(session)


@router.post("/workspaces", status_code=201)
async def create_workspace(payload: CreateWorkspaceIn,
                           session: AsyncSession = Depends(get_session)) -> dict:
    return await repository.create_workspace(
        session, name=payload.name,
        formulas=[f.model_dump() for f in payload.formulas],
        templates=[t.model_dump() for t in payload.templates])


@router.get("/workspaces/{workspace_id}")
async def get_workspace(workspace_id: str,
                        session: AsyncSession = Depends(get_session)) -> dict:
    try:
        return await repository.get_workspace(session, workspace_id)
    except repository.WorkspaceNotFoundError:
        raise HTTPException(status_code=404, detail="工作区不存在")


@router.put("/workspaces/{workspace_id}")
async def save_workspace(workspace_id: str, payload: SaveWorkspaceIn,
                         session: AsyncSession = Depends(get_session)) -> dict:
    try:
        return await repository.save_workspace(
            session, workspace_id, name=payload.name,
            expected_version=payload.expectedVersion,
            formulas=[f.model_dump() for f in payload.formulas],
            templates=[t.model_dump() for t in payload.templates])
    except repository.WorkspaceNotFoundError:
        raise HTTPException(status_code=404, detail="工作区不存在")
    except repository.ConcurrentModificationError as exc:
        raise HTTPException(status_code=409,
                            detail={"message": str(exc),
                                    "currentVersion": exc.current_version})


@router.delete("/workspaces/{workspace_id}", status_code=204)
async def delete_workspace(workspace_id: str,
                           session: AsyncSession = Depends(get_session)) -> None:
    try:
        await repository.delete_workspace(session, workspace_id)
    except repository.WorkspaceNotFoundError:
        raise HTTPException(status_code=404, detail="工作区不存在")
