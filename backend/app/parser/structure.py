"""LaTeX 结构解析：词法之上的配对与闭合检查。

唯一的解析核心是 ``check_structure`` 里的单一遍历 + 显式栈：
- 花括号/方括号/圆括号统一按结构配对（``\\frac{..}`` 等参数组也是普通花括号）；
- ``\\begin{env} ... \\end{env}`` 用环境帧处理，支持任意嵌套与名字一致性检查；
- ``\\left ... \\right`` 用 left 帧处理，检查定界符配对；
- 必选参数命令（``\\frac`` 等）只做 *前向元数校验*（参数组本身的配对仍由栈负责），
  因此不存在两条解析路径互相打架的问题。

所有错误都带行号/列号/偏移，错误位置契约：
- 缺少右括号/``\\right``/``\\end`` → offset 落在缺失处（源码末尾），消息中附左括号位置；
- 多余右括号/未知命令/定界符不配对 → offset 落在肇事 token 起点。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import spelling
from .lexer import (
    COMMAND, IGNORABLE, LBRACE, LBRACKET, LPAREN, RBRACE, RBRACKET, RPAREN,
    CLOSE_TO_OPEN, Token, line_column, tokenize,
)

# 必须带固定数量必选 {参数} 的命令
REQUIRED_ARGS = {
    "frac": 2, "dfrac": 2, "tfrac": 2,
    "sqrt": 1,
    "hat": 1, "widehat": 1, "tilde": 1, "widetilde": 1, "bar": 1,
    "overline": 1, "underline": 1, "vec": 1, "dot": 1, "ddot": 1,
    "breve": 1, "check": 1, "acute": 1, "grave": 1,
    "mathrm": 1, "mathbf": 1, "mathit": 1, "mathsf": 1, "mathtt": 1,
    "mathcal": 1, "mathbb": 1, "mathfrak": 1, "mathscr": 1,
    "operatorname": 1, "text": 1, "boxed": 1, "cancel": 1,
    "binom": 1, "dbinom": 1, "tbinom": 1,
    "label": 1, "ref": 1, "eqref": 1, "tag": 1,
}

_CLOSE_CHAR = {LBRACE: "}", LBRACKET: "]", LPAREN: ")"}
_OPEN_CHAR = {LBRACE: "{", LBRACKET: "[", LPAREN: "("}

_LEFT_DELIMS = {
    "[", "]", "(", ")", "{", "}", ".", "|", "/",
    "langle", "rangle", "lfloor", "rfloor", "lceil", "rceil",
    "lbrace", "rbrace", "lvert", "rvert", "lVert", "rVert",
    "uparrow", "downarrow", "updownarrow",
    "Uparrow", "Downarrow", "Updownarrow",
}
_DELIM_PAIRS = {
    "(": ")", "[": "]", "{": "}",
    "langle": "rangle", "lfloor": "rfloor", "lceil": "rceil",
    "lbrace": "rbrace", "lvert": "rvert", "lVert": "rVert",
    "|": "|", "/": "/",
}


@dataclass
class ParseError:
    code: str                 # 机器可读错误码
    message: str              # 可读提示（中文）
    offset: int               # 主错误位置（字符偏移，0 起）
    line: int
    column: int
    end_offset: int | None = None
    suggestion: str | None = None

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "offset": self.offset,
            "line": self.line,
            "column": self.column,
            "end_offset": self.end_offset,
            "suggestion": self.suggestion,
        }


@dataclass
class StructureResult:
    ok: bool
    errors: list[ParseError] = field(default_factory=list)
    tokens: list[Token] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "errors": [e.to_dict() for e in self.errors],
            "tokens": [t.to_dict() for t in self.tokens],
        }


@dataclass
class Frame:
    kind: str                 # 'brace' | 'left' | 'env'
    open_token: Token
    open_type: str | None = None    # brace 用
    env_name: str | None = None     # env 用
    delim: str | None = None        # left 用


def _err(code: str, message: str, source: str, offset: int,
         suggestion: str | None = None,
         end_offset: int | None = None) -> ParseError:
    line, col = line_column(source, offset)
    return ParseError(code, message, offset, line, col,
                      end_offset, suggestion)


def _cmd_name(tok: Token) -> str:
    """``\\frac`` -> ``frac``；``\\,`` 这类控制符号返回 ``,`。"""
    return tok.value[1:] if tok.value.startswith("\\") else tok.value


def _skip_ignorable(tokens: list[Token], idx: int) -> int:
    while idx < len(tokens) and tokens[idx].type in IGNORABLE:
        idx += 1
    return idx


def _delim_of(tok: Token | None) -> str | None:
    if tok is None:
        return None
    if tok.type == COMMAND:
        name = _cmd_name(tok)
        return name if name in _LEFT_DELIMS else None
    if tok.value in {"[", "]", "(", ")", "|", "/", "."}:
        return tok.value
    if tok.type == LBRACE:
        return "{"
    if tok.type == RBRACE:
        return "}"
    # 普通字符 token 可能含多个字符（词法把连续普通字符合并了），
    # 单字符 . 与 | 是合法定界符
    if tok.type not in (LBRACE, RBRACE) and len(tok.value) == 1 \
            and tok.value in (".", "|", "/"):
        return tok.value
    return None


def _disp_delim(d: str | None) -> str:
    if d in ("{", "}"):
        return "\\" + d
    return d or "?"


# ----------------------------------------------------------------- begin/end

def _read_env_name(tokens: list[Token], begin_idx: int,
                   errors: list[ParseError], source: str,
                   kind: str = "begin") -> tuple[str | None, int]:
    """解析 ``\\begin{name}`` / ``\\end{name}`` 中的环境名。

    返回 (名字或 None, name 后右花括号的下一个 token 下标)。
    """
    j = _skip_ignorable(tokens, begin_idx + 1)
    if j >= len(tokens) or tokens[j].type != LBRACE:
        errors.append(_err(
            "malformed_env",
            rf"\{kind} 后必须跟环境名，写成 \{kind}{{环境名}}",
            source, tokens[begin_idx].start,
            end_offset=tokens[begin_idx].end))
        return None, begin_idx + 1
    chars: list[str] = []
    depth = 1
    k = j + 1
    while k < len(tokens) and depth > 0:
        t = tokens[k]
        if t.type == LBRACE:
            depth += 1
            chars.append(t.value)
        elif t.type == RBRACE:
            depth -= 1
            if depth == 0:
                break
            chars.append(t.value)
        else:
            chars.append(t.value)
        k += 1
    if k >= len(tokens):
        errors.append(_err(
            "missing_rbrace",
            rf"\{kind} 的环境名缺少右花括号 }}",
            source, len(source)))
        return None, len(tokens)
    return "".join(chars).strip(), k + 1


# ------------------------------------------------------------- 必选参数校验

def _skip_balanced_group(tokens: list[Token], lbrace_idx: int) -> tuple[int, bool]:
    """从 LBRACE 下标跳到匹配 RBRACE 的下一位置；返回 (下标, 是否闭合)。"""
    depth = 1
    k = lbrace_idx + 1
    while k < len(tokens):
        t = tokens[k]
        if t.type == LBRACE:
            depth += 1
        elif t.type == RBRACE:
            depth -= 1
            if depth == 0:
                return k + 1, True
        k += 1
    return k, False


def _check_arity(cmd_tok: Token, tokens: list[Token], idx: int,
                 errors: list[ParseError], source: str,
                 unbalanced_tail: list[bool]) -> None:
    """前向校验命令是否带齐必选 ``{...}`` 参数（不改变栈，不消费 token）。

    unbalanced_tail[0] 为 True 时表示源码尾部已有未闭合花括号，
    “缺第二个参数”这类由同一根因导致的噪音不再重复报。
    """
    name = _cmd_name(cmd_tok)
    arity = REQUIRED_ARGS[name]
    k = _skip_ignorable(tokens, idx + 1)
    # sqrt 的可选参数 [..]
    if name == "sqrt" and k < len(tokens) and tokens[k].type == LBRACKET:
        depth = 1
        k += 1
        while k < len(tokens) and depth > 0:
            if tokens[k].type == LBRACKET:
                depth += 1
            elif tokens[k].type == RBRACKET:
                depth -= 1
            k += 1
    for arg_no in range(1, arity + 1):
        k = _skip_ignorable(tokens, k)
        if k >= len(tokens):
            if not unbalanced_tail[0]:
                errors.append(_err(
                    "missing_argument",
                    f"命令 {cmd_tok.value} 缺少第 {arg_no} 个必选 {{…}} 参数，"
                    "问题位置在公式末尾附近",
                    source, len(source)))
            return
        tok = tokens[k]
        if tok.type != LBRACE:
            errors.append(_err(
                "missing_argument",
                f"命令 {cmd_tok.value} 的第 {arg_no} 个参数缺少花括号："
                f"在 {tok.line} 行 {tok.column} 列附近遇到 {tok.value!r}，"
                "参数必须写成 {…}",
                source, tok.start, end_offset=tok.end))
            return
        nxt, closed = _skip_balanced_group(tokens, k)
        if not closed:
            # 未闭合组的 missing_rbrace 由栈统一报告，这里只标记根因
            unbalanced_tail[0] = True
            return
        k = nxt


# ----------------------------------------------------------------- 主解析

def check_structure(source: str) -> StructureResult:
    """对单段公式源码做完整结构校验。

    返回 :class:`StructureResult`：
    - ok：是否没有错误；
    - errors：ParseError 列表（code/message/offset/line/column/suggestion）；
    - tokens：词法 token 流（供前端高亮复用）。
    """
    tokens = tokenize(source)
    errors: list[ParseError] = []
    stack: list[Frame] = []
    unbalanced_tail = [False]

    i = 0
    while i < len(tokens):
        tok = tokens[i]

        # 开括号
        if tok.type in (LBRACE, LBRACKET, LPAREN):
            stack.append(Frame("brace", tok, open_type=tok.type))
            i += 1
            continue

        # 闭括号：弹到匹配帧
        if tok.type in (RBRACE, RBRACKET, RPAREN):
            wanted = CLOSE_TO_OPEN[tok.type]
            matched: Frame | None = None
            if tok.type == RBRACE:
                # 花括号是结构性分组：} 必须闭合最近的 {，中途帧按未闭合报告
                while stack:
                    top = stack.pop()
                    if top.kind == "brace" and top.open_type == wanted:
                        matched = top
                        break
                    _report_unclosed(top, errors, source)
                if matched is None:
                    errors.append(_err(
                        "unmatched_delimiter",
                        f"多余的右定界符 {tok.value!r}：找不到与之配对的 "
                        f"{_OPEN_CHAR[wanted]!r}",
                        source, tok.start, end_offset=tok.end))
            else:
                # [] 与 () 在数学模式里本质是对称符号：只闭合同一类型、
                # 且中间不跨花括号 / \left / 环境帧的开符号。
                # 跨边界时（如未闭合 { 组内的 ]）它只是普通字符，
                # 不提前触发“缺少 }”，从而保证缺括号错误定位仍在真正的缺失处。
                j = len(stack) - 1
                while j >= 0:
                    top = stack[j]
                    if top.kind == "brace" and top.open_type == wanted:
                        del stack[j:]
                        matched = top
                        break
                    if top.kind == "brace" or top.kind in ("left", "env"):
                        break  # 视为普通字符，不报错
                    j -= 1
                if matched is None and j < 0:
                    errors.append(_err(
                        "unmatched_delimiter",
                        f"多余的右定界符 {tok.value!r}：找不到与之配对的 "
                        f"{_OPEN_CHAR[wanted]!r}",
                        source, tok.start, end_offset=tok.end))
            i += 1
            continue

        if tok.type == COMMAND:
            name = _cmd_name(tok)

            if name == "begin":
                env_name, nxt = _read_env_name(tokens, i, errors, source, "begin")
                if env_name is not None:
                    stack.append(Frame("env", tok, env_name=env_name))
                i = nxt
                continue

            if name == "end":
                end_name, nxt = _read_env_name(tokens, i, errors, source, "end")
                top_env: Frame | None = None
                while stack:
                    top = stack.pop()
                    if top.kind == "env":
                        top_env = top
                        break
                    _report_unclosed(top, errors, source)
                if top_env is None:
                    errors.append(_err(
                        "unmatched_end",
                        r"\end 没有与之配对的 \begin",
                        source, tok.start, end_offset=tok.end))
                elif end_name is not None and end_name != top_env.env_name:
                    errors.append(_err(
                        "env_name_mismatch",
                        f"环境名不匹配：{tok.line} 行的 \\end{{{end_name}}} "
                        f"对应不上第 {top_env.open_token.line} 行开始的 "
                        f"\\begin{{{top_env.env_name}}}",
                        source, tok.start, end_offset=tok.end))
                i = nxt
                continue

            if name == "left":
                d_idx = _skip_ignorable(tokens, i + 1)
                d_tok = tokens[d_idx] if d_idx < len(tokens) else None
                delim = _delim_of(d_tok)
                if d_tok is None or delim is None:
                    errors.append(_err(
                        "bad_left_delimiter",
                        r"\left 后必须紧跟定界符（如 ( [ \{ . | 等）",
                        source, d_tok.start if d_tok else len(source),
                        end_offset=d_tok.end if d_tok else None))
                    i = d_idx if d_tok is not None else i + 1
                    continue
                stack.append(Frame("left", tok, delim=delim))
                i = d_idx + 1
                continue

            if name == "right":
                d_idx = _skip_ignorable(tokens, i + 1)
                d_tok = tokens[d_idx] if d_idx < len(tokens) else None
                delim = _delim_of(d_tok)
                top_left: Frame | None = None
                while stack:
                    top = stack.pop()
                    if top.kind == "left":
                        top_left = top
                        break
                    _report_unclosed(top, errors, source)
                if top_left is None:
                    errors.append(_err(
                        "unmatched_right",
                        r"\right 没有与之配对的 \left",
                        source, tok.start, end_offset=tok.end))
                elif delim is None:
                    errors.append(_err(
                        "bad_right_delimiter",
                        r"\right 后必须紧跟定界符（如 ) ] \} . | 等）",
                        source, d_tok.start if d_tok else len(source),
                        end_offset=d_tok.end if d_tok else None))
                elif delim not in (".",) and top_left.delim not in (".",):
                    expected = _DELIM_PAIRS.get(top_left.delim)
                    if expected is not None and delim != expected:
                        errors.append(_err(
                            "left_right_mismatch",
                            rf"\left{_disp_delim(top_left.delim)} 与 "
                            rf"\right{_disp_delim(delim)} 不配对",
                            source, d_tok.start, end_offset=d_tok.end))
                i = (d_idx + 1) if d_tok is not None else i + 1
                continue

            # 未知命令拼写检查
            if name and name[0].isalpha() and name not in spelling.KNOWN_UNIQUE:
                suggestion = spelling.suggest(name)
                if suggestion is not None:
                    errors.append(_err(
                        "unknown_command",
                        f"未知命令 {tok.value}：你是不是想写 \\{suggestion}？",
                        source, tok.start, suggestion=suggestion,
                        end_offset=tok.end))

            # 必选参数个数检查
            if name in REQUIRED_ARGS:
                _check_arity(tok, tokens, i, errors, source, unbalanced_tail)

            i += 1
            continue

        i += 1

    for frame in stack:
        _report_unclosed(frame, errors, source)

    return StructureResult(ok=not errors, errors=errors, tokens=tokens)


def _report_unclosed(frame: Frame, errors: list[ParseError],
                     source: str) -> None:
    ot = frame.open_token
    if frame.kind == "brace":
        closer = _CLOSE_CHAR[frame.open_type]
        errors.append(_err(
            "missing_rbrace" if frame.open_type == LBRACE else "missing_close",
            f"缺少右定界符 {closer!r}：第 {ot.line} 行第 {ot.column} 列的 "
            f"{_OPEN_CHAR[frame.open_type]!r} 没有闭合，缺失位置在公式末尾附近",
            source, len(source)))
    elif frame.kind == "left":
        errors.append(_err(
            "missing_right",
            rf"\left{_disp_delim(frame.delim)} 缺少配对的 \right"
            f"（\left 起始于第 {ot.line} 行第 {ot.column} 列）",
            source, len(source)))
    else:
        errors.append(_err(
            "missing_end",
            rf"环境 \begin{{{frame.env_name}}} 缺少 "
            rf"\end{{{frame.env_name}}}（起始于第 {ot.line} 行第 {ot.column} 列）",
            source, len(source)))
