"""AST node types produced by the structural parser.

All nodes carry ``start`` / ``end`` offsets into the original source so the
tolerant renderer and the segment slicer can map a node back to its exact
source span.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Node:
    start: int = 0
    end: int = 0


@dataclass
class TextNode(Node):
    """A run of ordinary characters.

    ``math`` records whether the run consists of math letters (rendered
    letter-by-letter as separate variables) versus literal text such as the
    argument of ``\\text{}``.
    """
    text: str = ""
    math: bool = True


@dataclass
class GlyphNode(Node):
    r"""A control sequence rendered as a single glyph, e.g. ``\alpha``."""
    command: str = ""
    char: str = ""
    kind: str = "normal"   # normal | bigop | function | spacing


@dataclass
class GroupNode(Node):
    """A ``{ ... }`` group (rendered without visible fences)."""
    children: list[Node] = field(default_factory=list)


@dataclass
class FracNode(Node):
    command: str = r"\frac"
    numerator: Node | None = None
    denominator: Node | None = None


@dataclass
class BinomNode(Node):
    command: str = r"\binom"
    upper: Node | None = None
    lower: Node | None = None


@dataclass
class SqrtNode(Node):
    radicand: Node | None = None
    degree: Node | None = None   # content of the optional [...] argument


@dataclass
class ScriptNode(Node):
    """Base/limit with subscript and/or superscript."""
    base: Node | None = None
    sub: Node | None = None
    sup: Node | None = None


@dataclass
class OverlineNode(Node):
    command: str = r"\overline"
    child: Node | None = None


@dataclass
class AccentNode(Node):
    command: str = r"\hat"
    accent: str = ""
    child: Node | None = None
    wide: bool = False


@dataclass
class FontNode(Node):
    r"""Style wrapper such as ``\mathbf{...}`` or plain ``\text{...}``."""
    command: str = r"\mathrm"
    variant: str | None = None   # None means upright text (\text)
    child: Node | None = None


@dataclass
class EnvNode(Node):
    """Matrix / cases / aligned environment."""
    name: str = ""
    rows: list[list[Node]] = field(default_factory=list)
    fence_left: str = ""
    fence_right: str = ""


@dataclass
class LeftRightNode(Node):
    r"""A ``\left<delim> ... \right<delim>`` fence pair."""
    children: list[Node] = field(default_factory=list)
    delim_left: str = "."
    delim_right: str = "."


@dataclass
class RefNode(Node):
    r"""A ``\ref{label}`` cross reference; resolved at preview time."""
    label: str = ""
    label_start: int = 0   # offset of the label text itself


@dataclass
class LabelNode(Node):
    r"""A ``\label{tag}`` declaration (inert in rendering)."""
    label: str = ""
    label_start: int = 0


@dataclass
class ErrNode(Node):
    """A fragment that could not be parsed; rendered as a red placeholder."""
    message: str = ""
    suggestion: str | None = None
    fatal: bool = False
