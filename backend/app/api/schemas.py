"""Pydantic request/response contracts for the HTTP API."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Formula / workspace payloads
# ---------------------------------------------------------------------------


class FormulaIn(BaseModel):
    clientId: str = Field(..., description="Stable client-side formula id")
    source: str = ""
    label: str | None = None


class TemplateIn(BaseModel):
    name: str
    code: str
    category: str = "自定义"


class WorkspaceSummary(BaseModel):
    id: str
    name: str
    version: int
    updatedAt: str | None = None


class WorkspaceOut(WorkspaceSummary):
    createdAt: str | None = None
    formulas: list[FormulaIn]
    templates: list[TemplateIn]


class CreateWorkspaceIn(BaseModel):
    name: str = "未命名工作区"
    formulas: list[FormulaIn] = []
    templates: list[TemplateIn] = []


class SaveWorkspaceIn(BaseModel):
    name: str
    expectedVersion: int
    formulas: list[FormulaIn]
    templates: list[TemplateIn] = []


# ---------------------------------------------------------------------------
# Parse / render / preview
# ---------------------------------------------------------------------------


class ParseIn(BaseModel):
    source: str
    tolerant: bool = False


class RenderIn(BaseModel):
    source: str
    tolerant: bool = True
    refs: dict[str, int] | None = None


class PreviewIn(BaseModel):
    formulas: list[FormulaIn]
    tolerant: bool = True
