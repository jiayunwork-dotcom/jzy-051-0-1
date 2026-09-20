"""Tolerant rendering and segment contracts.

Key invariant: a *local* error must never erase sibling content that is
perfectly renderable.
"""

from __future__ import annotations

from app.core import service
from app.core.parser import parse_source
from app.core.tolerant import render_segments, segments


def _render(source: str):
    r = parse_source(source)
    return render_segments(source, r.root, r.errors), r.errors


def test_missing_brace_still_renders_everything_around():
    source = r"a = \frac{1}{2} + \frac{3}{4"
    mathml, errors = _render(source)
    # Error detected at the second denominator's opening brace.
    assert errors[0].code == "missing_close_brace"
    # The intact first fraction and the 'a =' prefix survive.
    assert "<mfrac>" in mathml
    assert "<mn>1</mn>" in mathml
    assert "<mn>2</mn>" in mathml
    assert "<mi>a</mi>" in mathml
    # And the broken fragment is visibly marked, not silently dropped.
    assert 'class="latex-error"' in mathml


def test_unknown_command_placeholder_does_not_swallow_following_expression():
    source = r"x + \bogus + y^2"
    mathml, errors = _render(source)
    assert any(e.code == "unknown_command" for e in errors)
    assert 'class="latex-error"' in mathml
    assert "<msup>" in mathml          # y^2 still rendered
    assert "<mi>y</mi>" in mathml
    assert "<mi>x</mi>" in mathml


def test_segment_contract_good_bad_good():
    source = r"1+1 + \bogus + 2"
    r = parse_source(source)
    segs = segments(source, r.root, r.errors)
    kinds = [s.kind for s in segs]
    assert "error" in kinds
    # Segments are ordered, disjoint and cover the source.
    assert segs[0].start == 0
    assert segs[-1].end == len(source)
    for a, b in zip(segs, segs[1:]):
        assert a.end <= b.start
    error_seg = next(s for s in segs if s.kind == "error")
    assert r"\bogus" in error_seg.text


def test_segments_for_well_formed_source_are_all_ok():
    source = r"\frac{a}{b}+\sum_i x_i"
    r = parse_source(source)
    segs = segments(source, r.root, r.errors)
    assert all(s.kind != "error" for s in segs)
    assert any(s.kind == "ok" for s in segs)


def test_clean_formula_has_no_error_markers():
    mathml, errors = _render(r"\int_0^1 x^2\,dx")
    assert errors == []
    assert "latex-error" not in mathml
    assert "ref-error" not in mathml


def test_tolerant_service_mathml_always_present():
    out = service.render_formula(r"\frac{", tolerant=True)
    assert out["ok"] is False
    assert out["mathml"] is not None
    assert out["segments"]
    # Span contract fields.
    seg = out["segments"][0]
    assert set(seg) == {"kind", "start", "end", "text"}


def test_multiple_independent_errors_all_visible():
    source = r"\bogus_1 + \bogon_2"
    mathml, errors = _render(source)
    assert sum(e.code == "unknown_command" for e in errors) == 2
    assert mathml.count('class="latex-error"') >= 2
    # The '+' operator between the two errors is still rendered.
    assert mathml.count("<mo>+</mo>") == 1


def test_unclosed_left_right_renders_body():
    source = r"\left( \frac{a}{b}"
    mathml, errors = _render(source)
    assert any(e.code == "missing_right" for e in errors)
    assert "<mfrac>" in mathml
    assert "<mi>a</mi>" in mathml
    assert "<mi>b</mi>" in mathml


def test_unresolved_ref_is_a_loud_marker_not_a_number():
    out = service.render_formula(r"(\ref{nowhere})", tolerant=True)
    assert 'class="ref-error"' in out["mathml"]
    # It must not look like a valid numbered reference.
    assert 'class="formula-ref"' not in out["mathml"]
