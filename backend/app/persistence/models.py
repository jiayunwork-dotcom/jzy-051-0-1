"""ORM models for workspaces, their formulas and custom templates.

Concurrency model
-----------------
``workspaces.version`` is an optimistic-concurrency counter.  Every update
must include the version the client last saw; a mismatched version raises
:class:`ConcurrentModificationError` so two browser sessions saving the same
workspace can never silently overwrite each other.  Different workspaces are
independent rows and never block each other.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True,
                                   default=_uuid)
    name: Mapped[str] = mapped_column(Text, nullable=False, default="未命名工作区")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)

    formulas: Mapped[list["Formula"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan",
        order_by="Formula.position")
    templates: Mapped[list["CustomTemplate"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan",
        order_by="CustomTemplate.position")


class Formula(Base):
    __tablename__ = "formulas"

    id: Mapped[str] = mapped_column(String(36), primary_key=True,
                                   default=_uuid)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="")
    label: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    workspace: Mapped[Workspace] = relationship(back_populates="formulas")


class CustomTemplate(Base):
    __tablename__ = "custom_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True,
                                   default=_uuid)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False,
                                          default="自定义")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    workspace: Mapped[Workspace] = relationship(back_populates="templates")
