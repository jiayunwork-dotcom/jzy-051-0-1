"""Numbering and cross-reference kernel tests.

These guard the core invariant stated in the specification: after a
reorder, every formula number and every ``\\ref`` display must match the
new order; undefined labels, duplicate labels and reference cycles must all
be detected and reported rather than silently rendered with a wrong number.
"""

from __future__ import annotations

from app.core import service
from app.core.references import (
    FormulaInput,
    renumber,
    resolve_formulas,
)


def _formulas_with_refs():
    return [
        FormulaInput("a", r"a^2+b^2=c^2 \label{pythagoras}", "pythagoras"),
        FormulaInput("b", r"由 \ref{pythagoras} 可得 \ref{gauss}", None),
        FormulaInput("c", r"\mathcal{N}(x\mid\mu,\sigma^2) \label{gauss}",
                     "gauss"),
        FormulaInput("d", r"\ref{pythagoras},\ref{gauss}", None),
    ]


# ---------------------------------------------------------------------------
# Positional numbering
# ---------------------------------------------------------------------------


def test_numbers_are_positional_one_based():
    fs = _formulas_with_refs()
    res = resolve_formulas(fs)
    assert [f.number for f in res.formulas] == [1, 2, 3, 4]
    assert res.number_by_label == {"pythagoras": 1, "gauss": 3}


def test_renumber_is_just_list_order():
    fs = _formulas_with_refs()
    assert renumber(fs) == [1, 2, 3, 4]
    reordered = [fs[1], fs[3], fs[2], fs[0]]
    assert renumber(reordered) == [1, 2, 3, 4]  # positions, not stored


def test_reorder_updates_all_reference_numbers():
    fs = _formulas_with_refs()
    # Drag formula 'a' (pythagoras) to the end: [b, c, d, a]
    reordered = [fs[1], fs[2], fs[3], fs[0]]
    res = resolve_formulas(reordered)

    numbers = {f.client_id: f.number for f in res.formulas}
    assert numbers == {"b": 1, "c": 2, "d": 3, "a": 4}

    # gauss moved from #3 to #2; pythagoras moved from #1 to #4.
    b = res.formulas[0]
    assert b.ref_numbers == {"pythagoras": 4, "gauss": 2}

    d = res.formulas[2]
    assert d.ref_numbers == {"pythagoras": 4, "gauss": 2}

    assert res.number_by_label == {"pythagoras": 4, "gauss": 2}
    assert res.issues == []


def test_preview_contract_shows_resolved_numbers_after_reorder():
    fs = [
        {"clientId": "a", "source": r"\label{e} E=mc^2"},
        {"clientId": "b", "source": r"\ref{e}"},
    ]
    preview = service.preview_workspace([fs[1], fs[0]])
    assert preview["ok"] is True
    by_id = {f["clientId"]: f for f in preview["formulas"]}
    assert by_id["a"]["number"] == 2
    assert by_id["b"]["number"] == 1
    ref = by_id["b"]["references"][0]
    assert ref == {"label": "e", "line": 1, "column": 6, "number": 2,
                   "resolved": True}
    assert 'class="formula-ref">2</mi>' in by_id["b"]["mathml"]


# ---------------------------------------------------------------------------
# Undefined labels
# ---------------------------------------------------------------------------


def test_undefined_label_is_reported_with_position():
    res = resolve_formulas([
        FormulaInput("a", r"见 \ref{missing} 与 \ref{ghost}"),
    ])
    codes = [i.code for i in res.issues]
    assert codes == ["undefined_label", "undefined_label"]
    first = res.issues[0]
    assert first.label == "missing"
    assert first.formula_id == "a"
    # The offset must point at the label text inside \ref{...}, line 1:
    # 见=0, ' '=1, \=2 r=3 e=4 f=5 {=6, label starts at 7.
    assert (first.line, first.column) == (1, 8)
    assert "missing" in first.message

    # Nothing is rendered as a fabricated number.
    assert res.formulas[0].ref_numbers == {}


def test_render_uses_loud_placeholder_for_unresolved_ref():
    rendered = service.render_formula(r"\ref{ghost}", tolerant=True)
    assert 'class="ref-error"' in rendered["mathml"]
    assert rendered["segments"]  # non-empty contract


# ---------------------------------------------------------------------------
# Duplicate labels
# ---------------------------------------------------------------------------


def test_duplicate_labels_are_reported_on_every_owner():
    res = resolve_formulas([
        FormulaInput("a", r"\label{dup} 1"),
        FormulaInput("b", r"\label{dup} 2"),
        FormulaInput("c", r"\ref{dup}"),
    ])
    dup = [i for i in res.issues if i.code == "duplicate_label"]
    assert {i.formula_id for i in dup} == {"a", "b"}
    assert all("dup" in i.message for i in dup)
    # The referencing formula cannot resolve an ambiguous label either.
    undef = [i for i in res.issues if i.code == "undefined_label"]
    assert undef and undef[0].formula_id == "c"
    assert res.formulas[2].ref_numbers == {}


def test_inline_and_field_label_same_value_is_not_duplicate():
    # The metadata label and an inline \label agreeing is idempotent.
    res = resolve_formulas([
        FormulaInput("a", r"\label{x} 1", "x"),
    ])
    assert res.issues == []
    assert res.number_by_label == {"x": 1}


# ---------------------------------------------------------------------------
# Reference cycles
# ---------------------------------------------------------------------------


def test_mutual_reference_cycle_is_detected():
    res = resolve_formulas([
        FormulaInput("a", r"\label{a}\ref{b}"),
        FormulaInput("b", r"\label{b}\ref{a}"),
    ])
    cycles = [i for i in res.issues if i.code == "reference_cycle"]
    assert {i.formula_id for i in cycles} == {"a", "b"}
    cycle = cycles[0].cycle
    assert set(cycle) == {"a", "b"}
    # Numbers remain well-defined (positional) even with a cycle.
    assert [f.number for f in res.formulas] == [1, 2]


def test_three_formula_cycle_path_membership():
    res = resolve_formulas([
        FormulaInput("a", r"\label{a}\ref{c}"),
        FormulaInput("b", r"\label{b}\ref{a}"),
        FormulaInput("c", r"\label{c}\ref{b}"),
    ])
    cycles = [i for i in res.issues if i.code == "reference_cycle"]
    assert len(cycles) == 3
    assert all(set(i.cycle) == {"a", "b", "c"} for i in cycles)


def test_self_reference_is_a_cycle():
    res = resolve_formulas([
        FormulaInput("a", r"\label{self}\ref{self}"),
    ])
    assert [i.code for i in res.issues] == ["reference_cycle"]
    assert res.issues[0].cycle == ["a"]


def test_acyclic_chain_has_no_cycle_issue():
    res = resolve_formulas([
        FormulaInput("a", r"\label{a} 1"),
        FormulaInput("b", r"\label{b}\ref{a}"),
        FormulaInput("c", r"\label{c}\ref{b}\ref{a}"),
    ])
    assert res.issues == []
    assert res.formulas[2].ref_numbers == {"b": 2, "a": 1}
