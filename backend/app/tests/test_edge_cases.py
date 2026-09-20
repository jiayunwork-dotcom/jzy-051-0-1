"""Extra edge-case guards for positions and malformed commands."""

from __future__ import annotations

from app.core import service
from app.core.lexer import line_col
from app.core.parser import parse_source


def test_columns_count_unicode_characters():
    src = "见 \\ref{missing}"
    # 见=1, space=2, \=3..f=6, {=7, 'm' starts at column 8
    assert line_col(src, src.index("missing")) == (1, 8)
    assert parse_source(src).ok


def test_multiline_columns():
    src = "第一行很长很长\n  x = {"
    res = parse_source(src)
    err = res.errors[0]
    assert err.code == "missing_close_brace"
    assert err.line == 2
    assert err.column == 7


def test_ref_without_argument_is_flagged():
    res = parse_source(r"\ref")
    assert res.errors[0].code == "missing_ref_argument"


def test_ref_with_unclosed_brace_is_flagged():
    res = parse_source(r"x=\ref{")
    codes = [e.code for e in res.errors]
    assert "missing_close_brace" in codes


def test_double_script_is_flagged():
    res = parse_source("x_1_2")
    assert any(e.code == "double_script" for e in res.errors)


def test_sqrt_missing_closing_bracket():
    res = parse_source(r"\sqrt[3{x}")
    assert any(e.code == "missing_close_bracket" for e in res.errors)


def test_comment_is_inert():
    res = parse_source("% 这是注释 \\bogus\nx^2")
    assert res.ok


def test_empty_source_is_ok():
    assert parse_source("").ok
    out = service.render_formula("", tolerant=True)
    assert out["ok"] and "math" in out["mathml"]
