"""LaTeX lexer (tokenizer).

Input/output contract
---------------------
``tokenize(source)`` takes a raw formula source string and returns a list of
:class:`Token`.  Every token carries *start* and *end* offsets into the
source (half-open, ``end`` exclusive) plus a precomputed ``(line, column)``
for the **start** of the token, 1-based, counting characters (grapheme
agnostic — LaTeX source is assumed to be plain Unicode where 1 char == 1
column, which is good enough for error reporting).

Token kinds:

========  =============================================================
COMMAND   a control sequence, e.g. ``\\frac`` (includes the backslash)
CHAR      one structural character: ``{ } [ ] & ^ _ % $ #`` or ``\\``
TEXT      a run of ordinary characters (letters/digits/whitespace/...)
COMMENT   a ``% ...`` run including the ``%`` but NOT the trailing newline
========  =============================================================

The lexer never raises on malformed input: a dangling backslash at EOF is
emitted as a TEXT token so that the structural parser reports the error
with a precise position.
"""

from __future__ import annotations

from dataclasses import dataclass

# Single characters that are always their own token.
STRUCTURAL_CHARS = set("{}[]&^_$#%")

# A literal backslash not followed by a letter and not part of \\ (that is
# handled as the control sequence "\\").
@dataclass(frozen=True)
class Token:
    kind: str          # "COMMAND" | "CHAR" | "TEXT" | "COMMENT"
    text: str
    start: int
    end: int
    line: int
    column: int


def _line_col(source: str, offset: int) -> tuple[int, int]:
    """Return (1-based line, 1-based column) for *offset* in *source*."""
    line = source.count("\n", 0, offset) + 1
    last_nl = source.rfind("\n", 0, offset)
    column = offset - last_nl  # rfind returns -1 when no newline -> offset + 1
    return line, column


def tokenize(source: str) -> list[Token]:
    tokens: list[Token] = []
    i = 0
    n = len(source)
    text_start: int | None = None

    def flush_text() -> None:
        nonlocal text_start
        if text_start is not None:
            line, col = _line_col(source, text_start)
            tokens.append(Token("TEXT", source[text_start:i],
                                text_start, i, line, col))
            text_start = None

    while i < n:
        ch = source[i]

        # Comments run to the end of line; the newline stays in the stream
        # (as whitespace inside a TEXT token) which matches TeX behaviour.
        if ch == "%":
            flush_text()
            j = i + 1
            while j < n and source[j] != "\n":
                j += 1
            line, col = _line_col(source, i)
            tokens.append(Token("COMMENT", source[i:j], i, j, line, col))
            i = j
            continue

        if ch == "\\":
            flush_text()
            line, col = _line_col(source, i)
            # \\ is the line-break control sequence.
            if i + 1 < n and source[i + 1] == "\\":
                tokens.append(Token("COMMAND", "\\\\", i, i + 2, line, col))
                i += 2
                continue
            j = i + 1
            # Control symbol: backslash + one non-letter (including EOF).
            if j < n and not source[j].isalpha():
                end = j + 1
                tokens.append(Token("COMMAND", source[i:end], i, end,
                                    line, col))
                i = end
                continue
            # Control word: backslash followed by letters.
            while j < n and source[j].isalpha():
                j += 1
            if j == i + 1:  # lone trailing backslash
                tokens.append(Token("TEXT", "\\", i, i + 1, line, col))
                i += 1
            else:
                tokens.append(Token("COMMAND", source[i:j], i, j, line, col))
                i = j
            continue

        if ch in STRUCTURAL_CHARS:
            flush_text()
            line, col = _line_col(source, i)
            tokens.append(Token("CHAR", ch, i, i + 1, line, col))
            i += 1
            continue

        if text_start is None:
            text_start = i
        i += 1

    flush_text()
    return tokens


def line_col(source: str, offset: int) -> tuple[int, int]:
    """Public helper used by the parser/service layers."""
    return _line_col(source, offset)
