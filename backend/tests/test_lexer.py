"""词法切分测试。"""
from __future__ import annotations

from app.parser.lexer import (CHAR, COMMAND, COMMENT, LBRACE, NEWLINE,
                              RBRACE, SUP, tokenize)


def test_command_words_and_symbols():
    toks = tokenize(r"\frac \, \{")
    kinds = [(t.type, t.value) for t in toks]
    assert (COMMAND, r"\frac") in kinds
    assert (COMMAND, r"\,") in kinds
    assert (COMMAND, r"\{") in kinds


def test_braces_and_positions():
    toks = tokenize("{x}")
    assert [t.type for t in toks] == [LBRACE, CHAR, RBRACE]
    assert toks[0].start == 0
    assert toks[2].end == 3
    assert toks[0].line == 1 and toks[0].column == 1


def test_comment_runs_to_line_end_but_newline_kept():
    toks = tokenize("a % this is a comment\nb")
    types = [t.type for t in toks]
    assert COMMENT in types
    assert NEWLINE in types
    comment = next(t for t in toks if t.type == COMMENT)
    assert comment.value == "% this is a comment"
    b = toks[-1]
    assert b.line == 2 and b.column == 1


def test_line_numbers_multiline():
    src = "x\n\n y^2"
    toks = tokenize(src)
    sup = next(t for t in toks if t.type == SUP)
    assert sup.line == 3
