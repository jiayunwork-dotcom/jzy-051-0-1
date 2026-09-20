"""Structural LaTeX parser.

The parser consumes tokens from :mod:`app.core.lexer`, verifies brace /
``\\left...\\right`` / ``\\begin...\\end`` pairing and command closure and
builds the AST defined in :mod:`app.core.nodes`.

Contract
--------
``parse_source(source)`` returns :class:`ParseResult`:

* ``root``      — a :class:`~app.core.nodes.GroupNode` containing every top
  level node (never ``None``, even for empty / broken input);
* ``errors``    — ordered list of :class:`ParseError`;
* ``ok``        — ``True`` iff ``errors`` is empty.

The parser is *recovering*: whenever it can continue it does, inserting
:class:`~app.core.nodes.ErrNode` placeholders.  Callers that need strict
behaviour simply treat a non-empty error list as failure.  Thus the same
parse output powers both strict validation and tolerant rendering.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import commands as cmd
from .lexer import Token, line_col, tokenize
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
    OverlineNode,
    RefNode,
    BinomNode,
    ScriptNode,
    SqrtNode,
    TextNode,
)
from .spelling import suggest_command, suggest_env


@dataclass
class ParseError:
    code: str
    message: str
    offset: int
    length: int = 1
    line: int = 1
    column: int = 1
    suggestion: str | None = None

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "offset": self.offset,
            "length": self.length,
            "line": self.line,
            "column": self.column,
            "suggestion": self.suggestion,
        }


@dataclass
class ParseResult:
    root: GroupNode
    errors: list[ParseError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_blank(t: Token) -> bool:
    return t.kind == "TEXT" and t.text.strip() == ""


def _sig_tokens(source: str) -> list[Token]:
    """Comment-free token stream with ordinary TEXT runs expanded.

    Whitespace tokens are KEPT: the grammar needs to know whether a ``_`` /
    ``^`` directly follows its base (``+_{i}`` attaches to ``+``; the space
    in ``+ _{i}`` means the marker is dangling).  TeX treats each letter as
    its own atom, so multi-character TEXT runs are expanded per character so
    that ``E=mc^2`` binds the superscript to ``c`` only.
    """
    expanded: list[Token] = []
    for t in tokenize(source):
        if t.kind == "COMMENT":
            continue
        if t.kind == "TEXT" and len(t.text) > 1:
            for off, ch in enumerate(t.text):
                line, col = line_col(source, t.start + off)
                expanded.append(Token("TEXT", ch, t.start + off,
                                      t.start + off + 1, line, col))
        else:
            expanded.append(t)
    return expanded


@dataclass
class _Stream:
    """Result of parsing a contiguous slice of significant tokens."""
    children: list[Node]
    consumed: int            # number of input tokens consumed
    stop: str                # "brace" | "right" | "eof"
    stop_at: int | None = None  # index (in the slice) of the stopping token


_LEFTRIGHT_DELIMS = {
    "(", ")", "[", "]", "|", ".", "{", "}", "/", "\\",
}


class _Parser:
    def __init__(self, source: str) -> None:
        self.source = source
        self.toks = _sig_tokens(source)
        self.errors: list[ParseError] = []

    # -- error reporting ---------------------------------------------------

    def _err(self, code: str, message: str, offset: int, length: int = 1,
             suggestion: str | None = None) -> ParseError:
        line, col = line_col(self.source, offset)
        err = ParseError(code, message, offset, max(1, length), line, col,
                         suggestion)
        self.errors.append(err)
        return err

    # -- name group helper: "{matrix}" ------------------------------------

    def _read_name_group(self, toks: list[Token], i: int):
        """Read ``{name}`` starting at *i*.

        Returns ``(name, next_i, name_start_offset | None)`` where
        ``next_i`` points after the closing brace when present, otherwise
        simply after the consumed tokens.
        """
        if i >= len(toks) or toks[i].kind != "CHAR" or toks[i].text != "{":
            return None, i, None
        open_tok = toks[i]
        j = i + 1
        parts: list[str] = []
        name_start = toks[j].start if j < len(toks) else open_tok.end
        weird = False
        while j < len(toks):
            t = toks[j]
            if _is_blank(t):
                j += 1
                continue
            if t.kind == "CHAR" and t.text == "}":
                name = "".join(parts) if not weird else None
                return name, j + 1, name_start
            if t.kind == "TEXT":
                parts.append(t.text)
            elif t.kind == "COMMAND":
                # Environment names are plain letters; a control sequence
                # inside the braces means the name is malformed.
                weird = True
                parts.append(t.text)
            else:
                weird = True
                parts.append(t.text)
            j += 1
        self._err("missing_close_brace",
                  "缺少右花括号：环境名分组 “{” 未闭合，应在末尾补上 “}”。",
                  open_tok.start, 1)
        return ("".join(parts) if not weird else None), j, name_start

    # -- main entry --------------------------------------------------------

    def parse(self) -> ParseResult:
        stream = self._stream(self.toks, stops=())
        root = GroupNode(children=stream.children, start=0,
                         end=len(self.source))
        return ParseResult(root=root, errors=self.errors)

    def _stream(self, toks: list[Token], *,
                stops: tuple[str, ...] = ()) -> _Stream:
        """Parse tokens until EOF, an unmatched ``}`` or a stop command.

        ``stops`` may contain ``r"\\right"``.  Whitespace tokens are skipped
        (but see :meth:`_atom`: a ``_``/``^`` reached across whitespace is
        dangling rather than a trailing script).
        """
        children: list[Node] = []
        i = 0
        n = len(toks)
        while i < n:
            t = toks[i]
            if _is_blank(t):
                i += 1
                continue
            if t.kind == "COMMAND" and t.text in stops:
                return _Stream(children, i, "right", i)
            if t.kind == "CHAR" and t.text == "}":
                return _Stream(children, i, "brace", i)
            node, i = self._atom(toks, i)
            if node is not None:
                children.append(node)
        return _Stream(children, i, "eof", None)

    def _atom(self, toks: list[Token], i: int):
        """Parse one primary element *with* any immediately-adjacent scripts.

        A ``_``/``^`` attaches only when it is the very next token; if
        whitespace separates the marker from the base it is parsed as a new
        (dangling) atom instead.
        """
        t = toks[i]
        if t.kind == "CHAR" and t.text in ("_", "^"):
            err = self._err("dangling_script",
                            f"“{t.text}” 前面缺少作为下/上标主体的表达式。",
                            t.start)
            base = ErrNode(start=t.start, end=t.start, message=err.message)
            return self._build_scripts(toks, i, base)
        node, ni = self._single(toks, i)
        if ni < len(toks) and toks[ni].kind == "CHAR" \
                and toks[ni].text in ("_", "^"):
            return self._build_scripts(toks, ni, node)
        return node, ni

    # -- primary element ---------------------------------------------------

    def _single(self, toks: list[Token], i: int):
        """Parse exactly one primary element (no trailing scripts)."""
        t = toks[i]

        if t.kind == "CHAR" and t.text == "{":
            return self._group(toks, i)
        if t.kind == "CHAR" and t.text == "&":
            err = self._err("misplaced_alignment",
                            "此处出现了多余的对齐符 “&”，它只能用在矩阵或对齐环境中。",
                            t.start)
            return ErrNode(start=t.start, end=t.end, message=err.message,
                           fatal=False), i + 1
        if t.kind == "CHAR" and t.text in ("$", "#"):
            what = "数学定界符 “$”" if t.text == "$" else "参数符 “#”"
            err = self._err("unexpected_char",
                            f"公式中不应出现裸 {what}（数学环境已由编辑器提供）。",
                            t.start)
            return ErrNode(start=t.start, end=t.end, message=err.message), i + 1
        if t.kind == "CHAR":  # '[', ']' and other literal chars
            return TextNode(text=t.text, start=t.start, end=t.end), i + 1

        if t.kind == "COMMAND":
            return self._command(toks, i)

        # TEXT run
        return TextNode(text=t.text, start=t.start, end=t.end), i + 1

    def _group(self, toks: list[Token], i: int):
        open_tok = toks[i]
        inner = self._stream(toks[i + 1:], stops=())
        consumed = i + 1 + inner.consumed
        if inner.stop == "brace":
            close = toks[consumed]
            node = GroupNode(children=inner.children,
                             start=open_tok.start, end=close.end)
            return node, consumed + 1
        # Ran out of tokens without a closing brace.
        self._err("missing_close_brace",
                  "缺少右花括号：第 %d 行第 %d 列的 “{” 没有对应的 “}”，"
                  "请在该分组末尾补上 “}”。"
                  % (open_tok.line, open_tok.column),
                  open_tok.start, 1)
        marker = ErrNode(start=open_tok.start, end=open_tok.end,
                         message="缺少右花括号 “}”")
        node = GroupNode(children=[marker, *inner.children],
                         start=open_tok.start, end=self.source_end(toks))
        return node, consumed

    @staticmethod
    def source_end(toks: list[Token]) -> int:
        return toks[-1].end if toks else 0

    # -- commands ----------------------------------------------------------

    def _command(self, toks: list[Token], i: int):
        t = toks[i]
        name = t.text

        if name == r"\\":
            err = self._err("linebreak_outside_env",
                            "“\\\\” 只能用在矩阵、cases 等环境中换行。",
                            t.start, t.end - t.start)
            return ErrNode(start=t.start, end=t.end, message=err.message), i + 1

        if name == r"\begin":
            return self._env(toks, i)
        if name == r"\end":
            suggestion = None
            err = self._err("end_without_begin",
                            f"“\\end” 没有匹配的 “\\begin”。",
                            t.start, t.end - t.start, suggestion)
            # Skip a trailing {name} if present, it belongs to this \end.
            _, ni, _ = self._read_name_group(toks, i + 1)
            return ErrNode(start=t.start,
                           end=toks[ni - 1].end if ni > i + 1 else t.end,
                           message=err.message), ni

        if name == r"\left":
            return self._left(toks, i)
        if name == r"\right":
            err = self._err("right_without_left",
                            "“\\right” 没有匹配的 “\\left”。",
                            t.start, t.end - t.start)
            return ErrNode(start=t.start, end=t.end, message=err.message), i + 1

        if name == r"\ref":
            return self._ref_like(toks, i, is_ref=True)
        if name == r"\label":
            return self._ref_like(toks, i, is_ref=False)

        if name in cmd.SPACING:
            node = GlyphNode(command=name, char=cmd.GLYPH_COMMANDS.get(
                name, " "), kind="spacing", start=t.start, end=t.end)
            return self._scripts_after(toks, i + 1, node)

        if name in cmd.ARITY:
            return self._arity_command(toks, i)

        if name in cmd.GLYPH_COMMANDS:
            return self._glyph(toks, i)
        if name in cmd.FUNCTIONS:
            node = GlyphNode(command=name, char=name[1:], kind="function",
                             start=t.start, end=t.end)
            return self._scripts_after(toks, i + 1, node)
        if name in (r"\limits", r"\nolimits"):
            # Presentation hint; nothing to render.
            return None, i + 1
        if name in (r"\displaystyle", r"\textstyle", r"\scriptstyle",
                    r"\scriptscriptstyle"):
            return None, i + 1
        if name in (r"\quad", r"\qquad"):
            node = GlyphNode(command=name, char=" ",
                             kind="spacing", start=t.start, end=t.end)
            return self._scripts_after(toks, i + 1, node)

        suggestion = suggest_command(name)
        hint = f"，是否想写 “{suggestion}”？" if suggestion else ""
        err = self._err("unknown_command",
                        f"未知命令 “{name}”{hint}请检查拼写。",
                        t.start, t.end - t.start,
                        suggestion=suggestion)
        return ErrNode(start=t.start, end=t.end, message=err.message,
                       suggestion=suggestion), i + 1

    def _glyph(self, toks: list[Token], i: int):
        t = toks[i]
        name = t.text
        kind = "bigop" if name in cmd.BIG_OPERATORS else "normal"
        node = GlyphNode(command=name, char=cmd.GLYPH_COMMANDS[name],
                         kind=kind, start=t.start, end=t.end)
        return self._scripts_after(toks, i + 1, node)

    def _ref_like(self, toks: list[Token], i: int, *, is_ref: bool):
        t = toks[i]
        name = t.text
        label, ni, name_start = self._read_name_group(toks, i + 1)
        if ni == i + 1 or label is None:
            what = "引用标签" if is_ref else "标签名"
            err = self._err("missing_ref_argument",
                            f"“{name}” 后面必须紧跟形如 “{{标签}}” 的{what}。",
                            t.start, t.end - t.start)
            node = ErrNode(start=t.start, end=t.end, message=err.message)
            return node, ni
        cls = RefNode if is_ref else LabelNode
        node = cls(label=label, start=t.start,
                   end=toks[ni - 1].end, label_start=name_start)
        return self._scripts_after(toks, ni, node)

    def _arity_command(self, toks: list[Token], i: int):
        t = toks[i]
        name = t.text

        if name in (r"\frac", r"\dfrac", r"\tfrac"):
            ni, num = self._mandatory_arg(toks, i + 1, name, "分子")
            ni, den = self._mandatory_arg(toks, ni, name, "分母")
            end = self._node_end(toks, ni, num, den)
            node = FracNode(command=name, numerator=num, denominator=den,
                            start=t.start, end=end)
            return self._scripts_after(toks, ni, node)

        if name in (r"\binom", r"\dbinom", r"\tbinom"):
            ni, upper = self._mandatory_arg(toks, i + 1, name, "上项")
            ni, lower = self._mandatory_arg(toks, ni, name, "下项")
            node = BinomNode(command=name, upper=upper, lower=lower,
                             start=t.start,
                             end=self._node_end(toks, ni, upper, lower))
            return self._scripts_after(toks, ni, node)

        if name == r"\sqrt":
            ni = i + 1
            degree = None
            if ni < len(toks) and toks[ni].kind == "CHAR" \
                    and toks[ni].text == "[":
                open_sq = toks[ni]
                j = ni + 1
                cell: list[Node] = []
                while j < len(toks) and not (
                    toks[j].kind == "CHAR" and toks[j].text == "]"
                ):
                    if _is_blank(toks[j]):
                        cell.append(TextNode(text=toks[j].text,
                                             start=toks[j].start,
                                             end=toks[j].end))
                        j += 1
                        continue
                    node, j = self._atom(toks, j)
                    if node is not None:
                        cell.append(node)
                if j < len(toks):
                    degree = GroupNode(children=cell, start=open_sq.start,
                                       end=toks[j].end)
                    ni = j + 1
                else:
                    err = self._err("missing_close_bracket",
                                    "“\\sqrt[” 缺少与之配对的 “]”。",
                                    open_sq.start, 1)
                    degree = GroupNode(children=cell, start=open_sq.start,
                                       end=self.source_end(toks))
                    degree.children.append(ErrNode(
                        start=self.source_end(toks),
                        end=self.source_end(toks), message=err.message))
                    ni = j
            ni, radicand = self._mandatory_arg(toks, ni, name, "被开方内容")
            node = SqrtNode(radicand=radicand, degree=degree,
                            start=t.start,
                            end=self._node_end(toks, ni, radicand))
            return self._scripts_after(toks, ni, node)

        if name in (r"\overline", r"\underline"):
            ni, child = self._mandatory_arg(toks, i + 1, name, "参数")
            node = OverlineNode(command=name, child=child, start=t.start,
                                end=self._node_end(toks, ni, child))
            return self._scripts_after(toks, ni, node)

        if name in cmd.ACCENTS:
            ni, child = self._mandatory_arg(toks, i + 1, name, "参数")
            node = AccentNode(command=name, accent=cmd.ACCENTS[name],
                              child=child, wide=name in (r"\widehat",
                                                        r"\widetilde"),
                              start=t.start,
                              end=self._node_end(toks, ni, child))
            return self._scripts_after(toks, ni, node)

        if name in cmd.OVERS:
            ni, child = self._mandatory_arg(toks, i + 1, name, "参数")
            arrow, _where = cmd.OVERS[name]
            node = AccentNode(command=name, accent=arrow, child=child,
                              wide=True, start=t.start,
                              end=self._node_end(toks, ni, child))
            return self._scripts_after(toks, ni, node)

        if name in cmd.FONT_VARIANTS or name in (
            r"\text", r"\operatorname", r"\boldsymbol",
        ):
            ni, child = self._mandatory_arg(toks, i + 1, name, "参数")
            variant = cmd.FONT_VARIANTS.get(name)
            node = FontNode(command=name, variant=variant, child=child,
                            start=t.start,
                            end=self._node_end(toks, ni, child))
            return self._scripts_after(toks, ni, node)

        # Commands with declared arity but no dedicated branch: treat the
        # consumed argument groups as generic children (defensive).
        node = GlyphNode(command=name, char=name, kind="normal",
                         start=t.start, end=t.end)
        return self._scripts_after(toks, i + 1, node)

    def _node_end(self, toks: list[Token], ni: int, *nodes) -> int:
        if nodes:
            ends = [n.end for n in nodes if n is not None]
            if ends:
                return max(ends)
        return toks[ni - 1].end if ni > 0 and ni - 1 < len(toks) else 0

    def _mandatory_arg(self, toks: list[Token], i: int, command: str,
                       role: str):
        """Parse one mandatory command argument (a group or a single node)."""
        while i < len(toks) and _is_blank(toks[i]):
            i += 1
        if i >= len(toks):
            err = self._err(
                "missing_argument",
                f"“{command}” 缺少{role}参数，应写成 “{command}{{...}}”。",
                len(self.source), 1)
            return i, ErrNode(start=len(self.source),
                              end=len(self.source), message=err.message)
        t = toks[i]
        if t.kind == "CHAR" and t.text == "}":
            err = self._err(
                "missing_argument",
                f"“{command}” 缺少{role}参数：参数不能以 “}}” 提前结束。",
                t.start, 1)
            return i, ErrNode(start=t.start, end=t.start,
                              message=err.message)
        node, ni = self._atom(toks, i)
        if node is None:  # e.g. \limits consumed
            node = ErrNode(start=t.start, end=t.end,
                           message=f"“{command}” 的{role}参数为空。")
            self._err("missing_argument", node.message, t.start)
            ni = i + 1
        return ni, node

    # -- \left ... \right --------------------------------------------------

    def _left(self, toks: list[Token], i: int):
        left_tok = toks[i]
        j = i + 1
        while j < len(toks) and _is_blank(toks[j]):
            j += 1
        if j >= len(toks):
            err = self._err("missing_right",
                            "“\\left” 后缺少定界符以及配对的 “\\right”。",
                            left_tok.start, left_tok.end - left_tok.start)
            node = LeftRightNode(delim_left=".", delim_right=".",
                                 children=[ErrNode(
                                     start=left_tok.start,
                                     end=left_tok.end, message=err.message)],
                                 start=left_tok.start, end=left_tok.end)
            return node, j

        delim_tok = toks[j]
        left_delim, j = self._delim(toks, j)
        inner = self._stream(toks[j:], stops=(r"\right",))
        consumed = j + inner.consumed
        children = inner.children
        if inner.stop == "right":
            right_idx = consumed
            di = right_idx + 1
            while di < len(toks) and _is_blank(toks[di]):
                di += 1
            right_delim, after = self._delim(toks, di)
            end_tok_i = max(after - 1, right_idx)
            node = LeftRightNode(
                children=children, delim_left=left_delim,
                delim_right=right_delim, start=left_tok.start,
                end=toks[min(end_tok_i, len(toks) - 1)].end)
            return self._scripts_after(toks, after, node)

        # \left without matching \right (EOF or an enclosing '}').
        self._err("missing_right",
                  "“\\left” 缺少配对的 “\\right”（定界符 “%s” 未闭合）。"
                  % left_delim,
                  left_tok.start, delim_tok.end - left_tok.start)
        marker = ErrNode(start=left_tok.start, end=delim_tok.end,
                         message="缺少配对的 “\\right”")
        node = LeftRightNode(children=[marker, *children],
                             delim_left=left_delim,
                             delim_right=".", start=left_tok.start,
                             end=self.source_end(toks))
        return node, consumed

    def _delim(self, toks: list[Token], i: int):
        if i >= len(toks):
            return ".", i
        t = toks[i]
        if t.kind == "COMMAND":
            text = cmd.GLYPH_COMMANDS.get(t.text, t.text)
            if t.text == r"\|":
                text = "‖"
            return text, i + 1
        # A literal delimiter sits in a TEXT token that may also contain
        # surrounding spaces; take the first non-space character.
        stripped = t.text.lstrip()
        return (stripped[0] if stripped else "."), i + 1

    # -- environments ------------------------------------------------------

    def _env(self, toks: list[Token], i: int):
        begin_tok = toks[i]
        name, after_name, name_start = self._read_name_group(toks, i + 1)

        if name is None:
            err = self._err(
                "bad_begin",
                "“\\begin” 后必须紧跟合法的环境名分组，例如 “\\begin{matrix}”。",
                begin_tok.start, begin_tok.end - begin_tok.start)
            return ErrNode(start=begin_tok.start,
                           end=toks[after_name - 1].end
                           if after_name > i + 1 else begin_tok.end,
                           message=err.message), after_name

        if name not in cmd.KNOWN_ENVS:
            return self._skip_unknown_env(toks, i, name, after_name)

        return self._known_env(toks, i, name, after_name, begin_tok)

    def _skip_unknown_env(self, toks: list[Token], i: int, name: str,
                          after_name: int):
        begin_tok = toks[i]
        suggestion = suggest_env(name)
        hint = f"，是否想用 “{suggestion}”？" if suggestion else ""
        self._err("unknown_environment",
                  f"未知环境 “{name}”{hint}",
                  toks[i + 1].start if i + 1 < len(toks) else begin_tok.start,
                  len(name), suggestion=suggestion)
        # Skip the (possibly nested) body up to the matching \end{name}.
        depth = 1
        k = after_name
        while k < len(toks):
            if toks[k].kind == "COMMAND" and toks[k].text == r"\begin":
                inner_name, ni, _ = self._read_name_group(toks, k + 1)
                if inner_name == name:
                    depth += 1
                k = ni
                continue
            if toks[k].kind == "COMMAND" and toks[k].text == r"\end":
                end_name, ni, _ = self._read_name_group(toks, k + 1)
                if end_name == name:
                    depth -= 1
                    if depth == 0:
                        node = ErrNode(
                            start=begin_tok.start, end=toks[ni - 1].end,
                            message=f"未知环境 “{name}” 无法渲染。")
                        return self._scripts_after(toks, ni, node)
                k = ni
                continue
            k += 1
        self._err("missing_end",
                  f"环境 “\\begin{{{name}}}” 缺少配对的 “\\end{{{name}}}”。",
                  begin_tok.start, len(name))
        return ErrNode(start=begin_tok.start, end=self.source_end(toks),
                       message=f"未知环境 “{name}” 无法渲染。"), k

    def _known_env(self, toks: list[Token], i: int, name: str,
                   after_name: int, begin_tok: Token):
        # Linear scan: split the body into rows/cells on TOP-LEVEL '\\' and
        # '&' only (brace/environment depth 0), stopping at \end{name}.
        body = toks[after_name:]
        rows: list[list[list[Token]]] = [[[]]]
        brace_depth = 0
        env_depth = 0
        k = 0
        end_i: int | None = None
        body_n = len(body)
        while k < body_n:
            t = body[k]
            if t.kind == "CHAR" and t.text == "{":
                brace_depth += 1
                rows[-1][-1].append(t)
                k += 1
                continue
            if t.kind == "CHAR" and t.text == "}":
                brace_depth -= 1
                rows[-1][-1].append(t)
                k += 1
                continue
            if t.kind == "COMMAND" and t.text == r"\begin" \
                    and brace_depth == 0:
                env_depth += 1
                rows[-1][-1].append(t)
                k += 1
                continue
            if t.kind == "COMMAND" and t.text == r"\end" \
                    and brace_depth == 0 and env_depth == 0:
                end_name, end_ni, _ = self._read_name_group(body, k + 1)
                if end_name == name:
                    end_i = end_ni
                    break
                if end_name is not None:
                    self._err("mismatched_environment",
                              f"环境不匹配：当前打开的是 “\\begin{{{name}}}”，"
                              f"却用 “\\end{{{end_name}}}” 关闭。",
                              t.start, t.end - t.start)
                    # skip this wrong \end{...}, keep collecting
                    k = end_ni
                    continue
                k = end_ni
                continue
            if t.kind == "COMMAND" and t.text == r"\end" \
                    and brace_depth == 0 and env_depth > 0:
                env_depth -= 1
                rows[-1][-1].append(t)
                k += 1
                continue
            if brace_depth == 0 and env_depth == 0:
                if t.kind == "CHAR" and t.text == "&":
                    rows[-1].append([])
                    k += 1
                    continue
                if t.kind == "COMMAND" and t.text == r"\\":
                    rows.append([[]])
                    k += 1
                    continue
            rows[-1][-1].append(t)
            k += 1

        parsed_rows: list[list[Node]] = []
        for row in rows:
            parsed_rows.append([])
            for cell_tokens in row:
                stream = self._stream(cell_tokens, stops=())
                parsed_rows[-1].extend(stream.children)

        if end_i is None:
            self._err("missing_end",
                      f"环境 “\\begin{{{name}}}” 缺少配对的 "
                      f"“\\end{{{name}}}”。",
                      begin_tok.start, len(name))
            node = self._make_env_node(name, parsed_rows, begin_tok.start,
                                       self.source_end(toks))
            return node, after_name + k

        node = self._make_env_node(name, parsed_rows, begin_tok.start,
                                   body[end_i - 1].end)
        return self._scripts_after(toks, after_name + end_i, node)

    @staticmethod
    def _make_env_node(name: str, rows: list[list[Node]], start: int,
                       end: int) -> EnvNode:
        if name in cmd.MATRIX_FENCES:
            fl, fr = cmd.MATRIX_FENCES[name]
        else:
            fl = fr = ""
        return EnvNode(name=name, rows=rows, fence_left=fl,
                       fence_right=fr, start=start, end=end)

    # -- scripts -----------------------------------------------------------

    def _scripts_after(self, toks: list[Token], i: int, base: Node):
        """Attach any following _ / ^ to *base*."""
        if i < len(toks) and toks[i].kind == "CHAR" \
                and toks[i].text in ("_", "^"):
            return self._build_scripts(toks, i, base)
        return base, i

    def _build_scripts(self, toks: list[Token], i: int, base: Node):
        start = base.start
        script = ScriptNode(base=base, start=start, end=base.end)
        n = len(toks)
        while i < n and toks[i].kind == "CHAR" and toks[i].text in ("_", "^"):
            marker = toks[i]
            is_sub = marker.text == "_"
            existing = script.sub if is_sub else script.sup
            role = "下标" if is_sub else "上标"
            if existing is not None:
                self._err("double_script",
                          f"同一主体出现了两个{role}（重复的 “{marker.text}”）。",
                          marker.start)
                i += 1
                continue
            i += 1
            while i < n and _is_blank(toks[i]):
                i += 1
            if i >= n or (toks[i].kind == "CHAR"
                          and toks[i].text in ("}", "^", "_", "]")):
                err = self._err(
                    "missing_script_target",
                    f"“{marker.text}” 后面缺少{role}内容。",
                    marker.start)
                operand = ErrNode(start=marker.end, end=marker.end,
                                  message=err.message)
            else:
                # A script operand is a single primary element: the scripts
                # that follow a braced operand belong to the *outer* base
                # (so \int_{a}^{b} gives one msubsup, not nested scripts).
                operand, i = self._single(toks, i)
            if is_sub:
                script.sub = operand
            else:
                script.sup = operand
            if operand is not None:
                script.end = max(script.end, operand.end)
        return script, i


def parse_source(source: str) -> ParseResult:
    """Parse a formula *source* string into an AST plus parser errors."""
    return _Parser(source).parse()
