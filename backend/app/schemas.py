"""Pydantic 请求/响应模型（前后端契约）。"""
from __future__ import annotations

from pydantic import BaseModel, Field


# ----------------------------------------------------------------- 分析内核

class FormulaIn(BaseModel):
    id: str
    source: str = ""
    label: str | None = None


class AnalyzeRequest(BaseModel):
    formulas: list[FormulaIn]
    base: int = 1
    tolerant: bool = True
    fontsize: int = 18


class ParseRequest(BaseModel):
    source: str


# --------------------------------------------------------------- 工作区持久化

class WorkspaceSummary(BaseModel):
    id: str
    name: str
    version: int
    updated_at: str


class CreateWorkspaceRequest(BaseModel):
    name: str = "未命名工作区"
    formulas: list[FormulaIn] = Field(default_factory=list)
    templates: list[dict] = Field(default_factory=list)


class SaveWorkspaceRequest(BaseModel):
    name: str
    formulas: list[FormulaIn]
    templates: list[dict] = Field(default_factory=list)
    expected_version: int
