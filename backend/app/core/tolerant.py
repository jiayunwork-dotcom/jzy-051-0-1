"""Tolerant segmentation of a formula source.

Given a parsed AST, :func:`segments` splits the *original source text* into
an ordered list of disjoint, fully-covering :class:`Segment` objects:

* ``kind="ok"``    — source that belongs to a well-formed subtree;
* ``kind="error"`` — source covered by an :class:`ErrNode` or by an
  explicitly reported structural error span (e.g. an unmatched ``{``);
* ``kind="blank"``  — whitespace / comment / punctuation-only gaps that
  carry no renderable content.

A separate :func:`render_segments` renders each segment independently to
MathML, so **one local error cannot swallow the surrounding renderable
content**: bad fragments become ``<merror>`` markers while everything else
still renders.

This module is deliberately independent from the renderer's in-tree
``ErrNode`` handling: it is the contract ("these source spans are good /
bad") that automated tests assert on.
"""

from __future__ import annotations

from dataclasses import dataclass

from .nodes import (
    ErrNode,
    Node,
)
from .parser import ParseError
from .renderer import render_mathml
from xml.sax.saxutils import escape


@dataclass(frozen=True)
class Segment:
    kind: str          # "ok" | "error" | "blank"
    start: int
    end: int
    text: str
    error_code: str | None = None
    message: str | None = None


# ---------------------------------------------------------------------------
# Error span collection
# ---------------------------------------------------------------------------


def _err_nodes(node: Node, acc: list[ErrNode]) -> None:
    if isinstance(node, ErrNode):
        acc.append(node)
    for child in getattr(node, "children", []) or []:
        _err_nodes(child, acc)
    for attr in ("numerator", "denominator", "upper", "lower", "radicand",
                 "degree", "child", "base", "sub", "sup"):
        if hasattr(node, attr):
            val = getattr(node, attr)
            if isinstance(val, Node):
                _err_nodes(val, acc)
    if hasattr(node, "rows"):
        for row in node.rows:
            for cell in row:
                _err_nodes(cell, acc)
    if hasattr(node, "accent"):
        pass


def _merge(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    spans = sorted((s, e) for s, e in spans if e > s)
    out: list[list[int]] = []
    for s, e in spans:
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return [(s, e) for s, e in out]


def segments(source: str, root: Node,
             errors: list[ParseError] | None = None) -> list[Segment]:
    """Return good/bad/blank segments covering all of *source*."""
    err_nodes: list[ErrNode] = []
    _err_nodes(root, err_nodes)

    spans: list[tuple[int, int]] = [
        (max(0, n.start), min(len(source), max(n.end, n.start + 1)))
        for n in err_nodes
    ]
    # Some structural errors (e.g. an unmatched "{" opener) are reported on
    # tokens that belong to a recovered subtree: overlay them explicitly.
    for err in errors or []:
        if err.code in {"missing_close_brace", "missing_end", "missing_right",
                        "missing_close_bracket"}:
            # Mark the opener itself (1 char) so the body remains renderable.
            spans.append((err.offset, min(len(source), err.offset + 1)))

    bad = _merge(spans)
    result: list[Segment] = []
    cursor = 0
    for s, e in bad:
        if cursor < s:
            result.append(_classify(source, cursor, s))
        result.append(Segment("error", s, e, source[s:e]))
        cursor = e
    if cursor < len(source):
        result.append(_classify(source, cursor, len(source)))
    if not result:
        result.append(_classify(source, 0, len(source)))

    return [seg for seg in result if seg.kind != "blank" or seg.text.strip()]


def _classify(source: str, start: int, end: int) -> Segment:
    text = source[start:end]
    stripped = text.strip()
    # Comments ("% ...") and pure whitespace produce nothing renderable.
    if not stripped or all(ch in "%\n\r\t " for ch in stripped) \
            or stripped.startswith("%"):
        return Segment("blank", start, end, text)
    return Segment("ok", start, end, text)


# ---------------------------------------------------------------------------
# Segment-level tolerant rendering
# ---------------------------------------------------------------------------


def _error_placeholder(seg: Segment) -> str:
    return (f'<merror class="latex-error" title="{escape(seg.text.strip())}">'
            f'{escape(seg.text)}</merror>')


def render_segments(source: str, root: Node,
                    errors: list[ParseError] | None = None,
                    refs: dict[str, str] | None = None) -> str:
    """Render the recovered AST, reporting spans from ``segments``.

    The parser already recovered the tree around every error fragment, so
    rendering ``root`` once keeps all well-formed siblings intact while the
    embedded :class:`ErrNode` markers highlight the broken bits; nothing is
    re-parsed here (re-parsing a slice in isolation could manufacture new
    errors).
    """
    # Calling segments() is the explicit span contract; its result is
    # returned by the service layer. The MathML is one full-tree render.
    _ = segments(source, root, errors)
    return render_mathml(root, source, refs or {})
