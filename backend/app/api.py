"""FastAPI 路由。

- POST /api/analyze   多公式：编号重排、交叉引用、结构检查、后端渲染
- POST /api/parse     单段源码：词法 token + 结构错误（供编辑器高亮/提示）
- GET  /api/health    健康检查（含数据库连通性）
- 工作区 CRUD：/api/workspaces
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .db import repository
from .parser.structure import check_structure
from .schemas import (AnalyzeRequest, CreateWorkspaceRequest,
                      ParseRequest, SaveWorkspaceRequest)
from .services import analyze_formulas

router = APIRouter(prefix="/api")


@router.get("/health")
async def health() -> dict:
    try:
        pool = await repository._pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "ok", "database": "up"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "degraded", "database": str(exc)}


@router.post("/analyze")
async def analyze(req: AnalyzeRequest) -> dict:
    formulas = [f.model_dump() for f in req.formulas]
    return analyze_formulas(formulas, base=req.base,
                            tolerant=req.tolerant, fontsize=req.fontsize)


@router.post("/parse")
async def parse(req: ParseRequest) -> dict:
    result = check_structure(req.source)
    return result.to_dict()


# -------------------------------------------------------------- 工作区 API

@router.get("/workspaces")
async def list_workspaces() -> dict:
    return {"workspaces": await repository.list_workspaces()}


@router.post("/workspaces")
async def create_workspace(req: CreateWorkspaceRequest) -> dict:
    ws = await repository.create_workspace(
        name=req.name,
        formulas=[f.model_dump() for f in req.formulas],
        templates=req.templates,
    )
    return ws.to_dict()


@router.get("/workspaces/{workspace_id}")
async def get_workspace(workspace_id: str) -> dict:
    try:
        ws = await repository.get_workspace(workspace_id)
    except repository.WorkspaceNotFoundError:
        raise HTTPException(status_code=404, detail="工作区不存在")
    return ws.to_dict()


@router.put("/workspaces/{workspace_id}")
async def save_workspace(workspace_id: str, req: SaveWorkspaceRequest) -> dict:
    try:
        ws = await repository.save_workspace(
            workspace_id=workspace_id,
            name=req.name,
            formulas=[f.model_dump() for f in req.formulas],
            templates=req.templates,
            expected_version=req.expected_version,
        )
    except repository.WorkspaceNotFoundError:
        raise HTTPException(status_code=404, detail="工作区不存在")
    except repository.ConcurrentUpdateError as exc:
        raise HTTPException(status_code=409, detail={
            "message": str(exc),
            "expected_version": exc.expected,
            "actual_version": exc.actual,
        })
    return ws.to_dict()


@router.delete("/workspaces/{workspace_id}")
async def delete_workspace(workspace_id: str) -> dict:
    deleted = await repository.delete_workspace(workspace_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="工作区不存在")
    return {"deleted": True}
