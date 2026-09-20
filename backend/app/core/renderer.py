"""AST -> MathML renderer.

The frontend renders formulae by placing the MathML returned by the backend
directly into the DOM; no formula parsing ever happens in the browser.

``render_mathml(root, source, refs=None)``:

* ``root``   — parsed AST (see :mod:`app.core.parser`);
* ``source`` — original source text (used for :class:`ErrNode` snippets);
* ``refs``   — optional mapping ``label -> display string`` for ``\\ref``.
  Missing labels are rendered as red ``<merror>`` placeholders rather than
  wrong numbers.

The renderer is tolerant by construction: :class:`ErrNode` becomes a visible
``<merror>`` marker so a local mistake never blanks the whole formula.
"""

from __future__ import annotations

from xml.sax.saxutils import escape

from . import commands as cmd
from .nodes import (
    AccentNode,
    EnvNode,
    ErrNode,
    FontNode,
    FracNode,
    GlyphNode,
    GroupNode,
    LabelNode,
    LeftRightNode,
    Node,
    BinomNode,
    OverlineNode,
    RefNode,
    ScriptNode,
    SqrtNode,
    TextNode,
)

# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _e(text: str) -> str:
    return escape(text, {'"': "&quot;"})


def _seq(children, source: str, refs) -> str:
    return "".join(_render(c, source, refs) for c in children or [])


def _mi(text: str, variant: str | None = None) -> str:
    attr = f' mathvariant="{variant}"' if variant else ""
    return f"<mi{attr}>{_e(text)}</mi>"


def _mo(char: str, *, cls: str | None = None, stretchy: bool = False,
        fence: bool = False, largeop: bool = False) -> str:
    attrs = []
    if cls:
        attrs.append(f'class="{cls}"')
    if stretchy:
        attrs.append('stretchy="true"')
    if fence:
        attrs.append('fence="true"')
    if largeop:
        attrs.append('largeop="true"')
        attrs.append('movablelimits="true"')
    attr = (" " + " ".join(attrs)) if attrs else ""
    return f"<mo{attr}>{_e(char)}</mo>"


# ---------------------------------------------------------------------------
# Node rendering
# ---------------------------------------------------------------------------


def _render(node: Node, source: str, refs) -> str:
    if node is None:
        return ""

    if isinstance(node, TextNode):
        return _render_text(node.text)

    if isinstance(node, GroupNode):
        return _seq(node.children, source, refs)

    if isinstance(node, GlyphNode):
        return _render_glyph(node)

    if isinstance(node, FracNode):
        return (f"<mfrac>{_render(node.numerator, source, refs)}"
                f"{_render(node.denominator, source, refs)}</mfrac>")

    if isinstance(node, BinomNode):
        inner = (f"<mfrac linethickness='0'>"
                 f"{_render(node.upper, source, refs)}"
                 f"{_render(node.lower, source, refs)}</mfrac>")
        return (f"<mrow><mo fence='true'>(</mo>{inner}"
                f"<mo fence='true'>)</mo></mrow>")

    if isinstance(node, SqrtNode):
        if node.degree is not None:
            return (f"<mroot>{_render(node.radicand, source, refs)}"
                    f"{_render(node.degree, source, refs)}</mroot>")
        return f"<msqrt>{_render(node.radicand, source, refs)}</msqrt>"

    if isinstance(node, ScriptNode):
        return _render_script(node, source, refs)

    if isinstance(node, OverlineNode):
        tag = "mover" if node.command == r"\overline" else "munder"
        mark = "&#x000AF;" if node.command == r"\overline" else "&#x00332;"
        return (f"<{tag}>{_render(node.child, source, refs)}"
                f"<mo stretchy='true'>{mark}</mo></{tag}>")

    if isinstance(node, AccentNode):
        return (f"<mover>{_render(node.child, source, refs)}"
                f"<mo>{_e(node.accent)}</mo></mover>")

    if isinstance(node, FontNode):
        return _render_font(node, source, refs)

    if isinstance(node, EnvNode):
        return _render_env(node, source, refs)

    if isinstance(node, LeftRightNode):
        return _render_leftright(node, source, refs)

    if isinstance(node, RefNode):
        return _render_ref(node, refs)

    if isinstance(node, LabelNode):
        return ""  # \label declarations are invisible in the formula body

    if isinstance(node, ErrNode):
        return _render_error(node, source)

    return ""


def _render_text(text: str) -> str:
    out: list[str] = []
    for ch in text:
        if ch == "~":
            out.append('<mspace width="0.25em"></mspace>')
        elif ch.isspace():
            out.append(f"<mtext>{_e(ch)}</mtext>")
        elif ch.isdigit() or ch == ".":
            out.append(f"<mn>{_e(ch)}</mn>")
        elif ch in "+-/*=<>":
            out.append(_mo(ch))
        elif ch in "()[]|":
            out.append(_mo(ch, fence=True, stretchy=(ch == "|")))
        elif ch == ",":
            out.append(_mo(","))
        elif ch in ";:!?":
            out.append(f"<mo>{_e(ch)}</mo>")
        elif ch.isalpha():
            out.append(_mi(ch))
        else:
            out.append(_mo(ch))
    return "".join(out)


def _render_glyph(node: GlyphNode) -> str:
    ch = node.char
    if node.kind == "spacing":
        if node.command in cmd.SPACING:
            return f'<mspace width="{cmd.SPACING[node.command]}"></mspace>'
        width = "1em" if node.command == r"\quad" else "2em"
        return f'<mspace width="{width}"></mspace>'
    if node.kind == "bigop":
        return _mo(ch, largeop=True)
    if node.kind == "function":
        return f'<mo class="math-op">{_e(ch)}</mo>'
    if node.command in cmd.RELATIONS:
        return _mo(ch)
    if ch in "()[]{}|‖⟨⟩⌊⌋⌈⌉":
        return _mo(ch, stretchy=True)
    if ch in "+-/*=÷×⋅":
        return _mo(ch)
    return _mi(ch)


def _render_script(node: ScriptNode, source: str, refs) -> str:
    base = _render(node.base, source, refs)
    if node.sub is not None and node.sup is not None:
        return (f"<msubsup>{base}{_render(node.sub, source, refs)}"
                f"{_render(node.sup, source, refs)}</msubsup>")
    if node.sub is not None:
        return f"<msub>{base}{_render(node.sub, source, refs)}</msub>"
    if node.sup is not None:
        return f"<msup>{base}{_render(node.sup, source, refs)}</msup>"
    return base


def _render_font(node: FontNode, source: str, refs) -> str:
    body = _render(node.child, source, refs)
    if node.command == r"\operatorname":
        return f'<mstyle mathvariant="normal" class="operatorname">{body}</mstyle>'
    if node.command == r"\text":
        return f'<mstyle mathvariant="normal">{body}</mstyle>'
    variant = node.variant or "normal"
    # Re-tag the direct content with the variant.  Simplest robust approach:
    # wrap in <mstyle mathvariant=...>, which affects nested <mi> tokens.
    return f'<mstyle mathvariant="{variant}">{body}</mstyle>'


def _text_of(node: Node) -> str:
    """Flatten a node tree to plain text (used inside \\text{})."""
    if node is None:
        return ""
    if isinstance(node, TextNode):
        return node.text
    if isinstance(node, GlyphNode):
        return node.char
    if isinstance(node, RefNode):
        return node.label
    children = getattr(node, "children", None)
    if children is not None:
        return "".join(_text_of(c) for c in children)
    for attr in ("child", "numerator", "denominator", "upper", "lower",
                 "radicand", "degree", "base", "sub", "sup"):
        if hasattr(node, attr):
            val = getattr(node, attr)
            if isinstance(val, Node):
                return _text_of(val)
    if isinstance(node, EnvNode):
        return ""
    return ""


def _render_env(node: EnvNode, source: str, refs) -> str:
    colsep = '<mrow><mo>&amp;</mo></mrow>'
    rows_xml: list[str] = []
    for row in node.rows:
        cells: list[str] = []
        for child in row:
            if isinstance(child, GlyphNode) and child.kind == "align-sep":
                cells.append("<mrow></mrow>")
                continue
            cells.append(f"<mrow>{_render(child, source, refs)}</mrow>")
        # Every row must expose the same number of <mtd> cells.
        rows_xml.append("<mtr>" + "".join(
            f"<mtd>{c}</mtd>" for c in cells) + "</mtr>")
    table = (f'<mtable columnalign="left">{ "".join(rows_xml) }</mtable>'
             if node.name in cmd.ALIGN_ENVS
             else f"<mtable>{''.join(rows_xml)}</mtable>")

    if node.name == "cases":
        return (f"<mrow><mo fence='true' stretchy='true'>{{</mo>"
                f"{table}</mrow>")
    if node.name in ("aligned", "split"):
        return table
    fl, fr = node.fence_left, node.fence_right
    left = _mo(fl, fence=True, stretchy=True) if fl else ""
    right = _mo(fr, fence=True, stretchy=True) if fr else ""
    return f"<mrow>{left}{table}{right}</mrow>"


def _render_leftright(node: LeftRightNode, source: str, refs) -> str:
    body = _seq(node.children, source, refs)
    left = _mo(node.delim_left, fence=True, stretchy=True) \
        if node.delim_left != "." else ""
    right = _mo(node.delim_right, fence=True, stretchy=True) \
        if node.delim_right != "." else ""
    return f"<mrow>{left}{body}{right}</mrow>"


def _render_ref(node: RefNode, refs) -> str:
    if refs is not None and node.label in refs:
        return f'<mi class="formula-ref">{_e(str(refs[node.label]))}</mi>'
    # Unresolved reference — loud placeholder, never a silent wrong number.
    return (f'<merror class="ref-error" title="未定义的引用标签 '
            f'{_e(node.label)}">?{_e(node.label)}?</merror>')


def _render_error(node: ErrNode, source: str) -> str:
    snippet = source[node.start:node.end] if node.end > node.start \
        else "∎"
    title = _e(node.message)
    return (f'<merror class="latex-error" title="{title}">'
            f'{_e(snippet)}</merror>')


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def render_mathml(root: Node, source: str,
                  refs: dict[str, str] | None = None) -> str:
    body = _render(root, source, refs if refs is not None else {})
    return (f'<math xmlns="http://www.w3.org/1998/Math/MathML" '
            f'display="block" class="formula-math">{body}</math>')
