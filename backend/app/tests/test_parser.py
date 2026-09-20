"""Structural parser tests: pairing, error location and spellcheck."""

from __future__ import annotations

import pytest

from app.core import service
from app.core.lexer import tokenize
from app.core.parser import parse_source
from app.core.spelling import damerau_levenshtein, suggest_command, suggest_env


# ---------------------------------------------------------------------------
# Happy-path pairing
# ---------------------------------------------------------------------------


def test_balanced_sources_parse_cleanly():
    for src in [
        r"\frac{a}{b}",
        r"\left(\frac{1}{2}\right)",
        r"\begin{pmatrix}1&2\\3&4\end{pmatrix}",
        r"\sqrt[3]{x}+\sqrt{y}",
        r"\left\{\,x\in\mathbb{R}\mid x>0\,\right\}",
        r"x_{i}^{2}",
        r"\text{if }x>0",
    ]:
        result = parse_source(src)
        assert result.ok, f"{src!r}: {[e.message for e in result.errors]}"


# ---------------------------------------------------------------------------
# Missing closing brace — location must point at the real opening brace
# ---------------------------------------------------------------------------


def test_missing_close_brace_reports_opener_position():
    source = r"\frac{1}{2"  # denominator opening brace at index 8
    result = parse_source(source)
    assert not result.ok
    err = result.errors[0]
    assert err.code == "missing_close_brace"
    assert source[err.offset] == "{"
    assert err.offset == 8
    assert (err.line, err.column) == (1, 9)
    assert "}" in err.message


def test_missing_close_brace_on_multiline_source():
    source = "\n\n  x = {a + b"
    result = parse_source(source)
    err = result.errors[0]
    assert err.code == "missing_close_brace"
    assert source[err.offset] == "{"
    assert (err.line, err.column) == (3, 7)


def test_unclosed_environment_is_reported_at_begin():
    source = r"\begin{cases} a & b "
    result = parse_source(source)
    codes = [e.code for e in result.errors]
    assert "missing_end" in codes
    err = next(e for e in result.errors if e.code == "missing_end")
    assert err.offset == 0  # the \begin opener


def test_missing_right_reports_left():
    source = r"\left(\frac{1}{2}"
    result = parse_source(source)
    codes = [e.code for e in result.errors]
    assert "missing_right" in codes
    err = next(e for e in result.errors if e.code == "missing_right")
    assert source[err.offset:].startswith(r"\left")


def test_mismatched_environment_names():
    source = r"\begin{pmatrix}1\end{cases}"
    result = parse_source(source)
    codes = [e.code for e in result.errors]
    assert "mismatched_environment" in codes or "missing_end" in codes


def test_end_without_begin():
    result = parse_source(r"\end{matrix}")
    assert result.errors[0].code == "end_without_begin"


def test_right_without_left():
    result = parse_source(r"x\right)")
    assert result.errors[0].code == "right_without_left"


def test_missing_command_argument():
    result = parse_source(r"\frac{a}")
    codes = [e.code for e in result.errors]
    assert "missing_argument" in codes


def test_dangling_script():
    result = parse_source(r"x + _{i}")
    assert any(e.code == "dangling_script" for e in result.errors)


# ---------------------------------------------------------------------------
# Unknown commands and spelling suggestions
# ---------------------------------------------------------------------------


def test_unknown_command_is_flagged():
    result = parse_source(r"\foobar{x}")
    err = result.errors[0]
    assert err.code == "unknown_command"
    assert err.suggestion is None


@pytest.mark.parametrize("typo,expected", [
    (r"\alhpa", r"\alpha"),       # transposition
    (r"\gama", r"\gamma"),        # substitution
    (r"\inte", r"\int"),          # deletion-ish
    (r"\summ", r"\sum"),
    (r"\rightaarrow", r"\rightarrow"),
])
def test_spelling_suggestions(typo, expected):
    assert suggest_command(typo) == expected


def test_unknown_command_carries_suggestion():
    result = parse_source(r"\alhpa_i")
    err = next(e for e in result.errors if e.code == "unknown_command")
    assert err.suggestion == r"\alpha"
    assert r"\alpha" in err.message


def test_unknown_environment_suggestion():
    assert suggest_env("pmatri") == "pmatrix"
    result = parse_source(r"\begin{pmatri}1\end{pmatri}")
    assert any(e.code == "unknown_environment"
               and e.suggestion == "pmatrix" for e in result.errors)


def test_short_garbage_gets_no_suggestion():
    assert suggest_command(r"\zzz") is None


def test_damerau_metric_basics():
    assert damerau_levenshtein("abc", "abc") == 0
    assert damerau_levenshtein("abc", "acb") == 1   # transposition
    assert damerau_levenshtein("", "ab") == 2


# ---------------------------------------------------------------------------
# Lexer positions
# ---------------------------------------------------------------------------


def test_lexer_offsets_and_comments():
    toks = tokenize("ab % comment\n\\frac")
    kinds = [(t.kind, t.text) for t in toks]
    assert ("COMMENT", "% comment") in kinds
    cmd = next(t for t in kinds if t[0] == "COMMAND")
    assert cmd[1] == r"\frac"
    frac = next(t for t in toks if t.text == r"\frac")
    assert frac.line == 2


# ---------------------------------------------------------------------------
# Strict vs tolerant service contract
# ---------------------------------------------------------------------------


def test_strict_service_returns_no_mathml_on_error():
    out = service.parse_formula(r"\frac{")
    assert out["ok"] is False
    assert out["errors"] and out["errors"][0]["line"] >= 1


def test_render_strict_returns_none_mathml_on_error():
    out = service.render_formula(r"\frac{", tolerant=False)
    assert out["ok"] is False
    assert out["mathml"] is None
