"""LaTeX 词法分析器。

输入：任意字符串（公式源码）。
输出：Token 列表，每个 token 带有类型、原文切片、起始偏移、行号、列号（均从 1 起）。

该模块只做词法切分，不判断配对是否正确——配对由 structure 模块负责。
前端高亮也复用同一套 token 类型约定（经 /api/parse 返回）。
"""
from __future__ import annotations

from dataclasses import dataclass

# ---- token 类型 ---------------------------------------------------------
COMMAND = "command"          # \frac 或 \{ 等控制符
LBRACE = "lbrace"            # {
RBRACE = "rbrace"            # }
LBRACKET = "lbracket"        # [
RBRACKET = "rbracket"        # ]
LPAREN = "lparen"            # (
RPAREN = "rparen"            # )
SUP = "sup"                  # ^
SUB = "sub"                  # _
ALIGN = "align"              # &
SPACE = "space"              # 空格 / tab（不含换行）
NEWLINE = "newline"          # \n
COMMENT = "comment"          # % 到行尾
DOLLAR = "dollar"            # $
NBSP = "nbsp"                # ~
PIPE = "pipe"                # | （\left| 等定界符）
CHAR = "char"                # 其它普通字符

BRACE_PAIRS = {
    LBRACE: RBRACE,
    LBRACKET: RBRACKET,
    LPAREN: RPAREN,
}
CLOSE_TO_OPEN = {v: k for k, v in BRACE_PAIRS.items()}


@dataclass(frozen=True)
class Token:
    type: str
    value: str
    start: int
    end: int       # 半开区间
    line: int
    column: int

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "value": self.value,
            "start": self.start,
            "end": self.end,
            "line": self.line,
            "column": self.column,
        }


def line_column(source: str, pos: int) -> tuple[int, int]:
    """把字符偏移转换为 (行号, 列号)，均从 1 开始；pos 允许等于 len(source)。"""
    pos = max(0, min(pos, len(source)))
    line = 1
    col = 1
    for i, ch in enumerate(source):
        if i >= pos:
            break
        if ch == "\n":
            line += 1
            col = 1
        else:
            col += 1
    return line, col


def tokenize(source: str) -> list[Token]:
    """把源码切分为 token 流。

    规则：
    - 反斜杠后跟字母：吃尽可能长的字母串（控制词）
    - 反斜杠后跟非字母：该单个字符构成控制符（包括 ``\\{``、``\\,``、``\\ `` 等）
    - ``%``：注释一直吃到行尾（不含换行符，保证行号正确）
    """
    tokens: list[Token] = []
    n = len(source)
    i = 0
    line, col = 1, 1

    def emit(ttype: str, value: str, start: int) -> None:
        ln, c = line_column(source, start)
        tokens.append(Token(ttype, value, start, start + len(value), ln, c))

    while i < n:
        ch = source[i]

        if ch == "\\":
            # 控制序列
            if i + 1 >= n:
                emit(COMMAND, "\\", i)
                i += 1
                continue
            nxt = source[i + 1]
            if nxt.isalpha():
                j = i + 1
                while j < n and source[j].isalpha():
                    j += 1
                emit(COMMAND, source[i:j], i)
                i = j
            else:
                # 控制符号恰好两个字符（\， \, ， \{ …）
                emit(COMMAND, source[i:i + 2], i)
                i += 2
            continue

        simple = {
            "{": LBRACE,
            "}": RBRACE,
            "[": LBRACKET,
            "]": RBRACKET,
            "(": LPAREN,
            ")": RPAREN,
            "^": SUP,
            "_": SUB,
            "&": ALIGN,
            "~": NBSP,
            "|": PIPE,
            "$": DOLLAR,
        }
        if ch in simple:
            emit(simple[ch], ch, i)
            i += 1
            continue

        if ch == "%":
            j = i + 1
            while j < n and source[j] != "\n":
                j += 1
            emit(COMMENT, source[i:j], i)
            i = j
            continue

        if ch in " \t\r":
            j = i + 1
            while j < n and source[j] in " \t\r":
                j += 1
            emit(SPACE, source[i:j], i)
            i = j
            continue

        if ch == "\n":
            emit(NEWLINE, ch, i)
            i += 1
            continue

        # 普通字符：连续的同类普通字符合并，便于前端高亮
        j = i + 1
        while j < n and source[j] not in "\\{}[]()^&~|$% \t\r\n":
            j += 1
        emit(CHAR, source[i:j], i)
        i = j

    return tokens


# 解析时应忽略其存在的 token（注释与空白不影响结构）
IGNORABLE = (COMMENT, SPACE, NEWLINE)
