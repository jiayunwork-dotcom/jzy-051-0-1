"""编号重排与交叉引用正确性测试（后端可独立验证的核心）。

覆盖：
- 顺序编号；
- 重新排序后编号与所有 \\ref 显示同步更新；
- 三类异常：引用不存在标签 / 重复标签 / 成环引用；
- \\eqref 显示带括号编号。
"""
from __future__ import annotations

from app.xrefs.numbering import extract_labels, extract_refs, resolve


def f(fid, source="", label=None):
    return {"id": fid, "source": source, "label": label}


def test_sequential_numbers_follow_position_only():
    result = resolve([f("a", "x"), f("b", "y"), f("c", "z")], base=1)
    assert result.ok
    assert [x.number for x in result.formulas] == [1, 2, 3]


def test_base_offset():
    result = resolve([f("a"), f("b")], base=3)
    assert [x.number for x in result.formulas] == [3, 4]


def test_ref_resolves_to_target_number():
    formulas = [
        f("energy", r"E=mc^2 \label{energy}"),
        f("cite", r"see \ref{energy} above"),
    ]
    result = resolve(formulas)
    assert result.ok
    assert result.label_to_number == {"energy": 1}
    cite = result.formulas[1]
    assert cite.refs[0].number == 1
    assert cite.rendered_source == "see 1 above"


def test_eqref_renders_parenthesized_number():
    result = resolve([
        f("a", r"x \label{x}"),
        f("b", r"as in \eqref{x}"),
    ])
    assert result.ok
    assert result.formulas[1].rendered_source == "as in (1)"


def test_reorder_renumbers_everything_and_all_refs_follow():
    # A 引用 B 的标签；交换顺序后 A 是 2、B 是 1，A 中的引用必须变成 1
    formulas = [
        f("A", r"from \ref{planck} we derive"),
        f("B", r"E=\hbar\omega \label{planck}"),
    ]
    first = resolve(formulas)
    assert first.formulas[0].rendered_source == "from 2 we derive"
    assert first.label_to_number == {"planck": 2}

    reordered = [formulas[1], formulas[0]]
    second = resolve(reordered)
    assert [x.number for x in second.formulas] == [1, 2]
    assert second.label_to_number == {"planck": 1}
    # 现在 A 是第二个公式，它里面的引用显示必须更新为 B 的新编号 1
    a = next(x for x in second.formulas if x.id == "A")
    assert a.number == 2
    assert a.refs[0].number == 1
    assert a.rendered_source == "from 1 we derive"


def test_reorder_chain_of_references():
    # 三个公式构成无环引用链；整体逆序后每个引用的数字都必须与新顺序一致
    formulas = [
        f("f1", r"a \label{one}"),
        f("f2", r"\label{two}\ref{one}+1"),
        f("f3", r"\ref{one},\ref{two}"),
    ]
    first = resolve(formulas)
    assert first.formulas[1].rendered_source.strip() == "1+1"
    assert first.formulas[2].refs[0].number == 1
    assert first.formulas[2].refs[1].number == 2

    rev = list(reversed(formulas))
    second = resolve(rev)
    assert [x.number for x in second.formulas] == [1, 2, 3]
    f3_new = second.formulas[0]   # 原 f3
    f2_new = second.formulas[1]
    f1_new = second.formulas[2]
    # f3 里两个引用分别指向新编号 3（one）和 2（two）
    assert [r.number for r in f3_new.refs] == [3, 2]
    # f2 里的引用也变成 3
    assert f2_new.refs[0].number == 3
    assert "3+1" in f2_new.rendered_source
    assert f1_new.number == 3


def test_undefined_label_is_detected_and_never_silently_numbered():
    result = resolve([
        f("a", r"see \ref{ghost}"),
    ])
    assert not result.ok
    codes = {e.code for e in result.errors}
    assert "undefined_label" in codes
    ref = result.formulas[0].refs[0]
    assert ref.number is None
    assert ref.error_code == "undefined_label"
    # 不允许渲染出一个错号：替换为占位
    assert r"\boxed{?}" in result.formulas[0].rendered_source
    err = next(e for e in result.errors if e.code == "undefined_label")
    assert err.formula_id == "a"
    assert err.label == "ghost"
    assert err.line == 1 and err.column == 5  # \ref 在第 5 列


def test_duplicate_labels_are_detected():
    result = resolve([
        f("a", r"\label{dup} x"),
        f("b", r"\label{dup} y"),
        f("c", r"\ref{dup}"),
    ])
    codes = {e.code for e in result.errors}
    assert "duplicate_label" in codes
    assert "duplicate_label_target" in codes
    # 重复标签不得出现在确定的 label_to_number 里
    assert "dup" not in result.label_to_number
    c = result.formulas[2]
    assert c.refs[0].number is None
    assert r"\boxed{?}" in c.rendered_source


def test_self_reference_is_a_cycle():
    result = resolve([
        f("a", r"\ref{loop} x \label{loop}"),
    ])
    assert any(e.code == "ref_cycle" for e in result.errors)
    assert r"\boxed{?}" in result.formulas[0].rendered_source


def test_mutual_reference_cycle_is_detected():
    # A 引用 B、B 引用 A
    result = resolve([
        f("A", r"\ref{b-label} ... \label{a-label}"),
        f("B", r"\ref{a-label} ... \label{b-label}"),
    ])
    cycle_errors = [e for e in result.errors if e.code == "ref_cycle"]
    assert len(cycle_errors) == 2
    involved = {e.formula_id for e in cycle_errors}
    assert involved == {"A", "B"}
    # 成环的引用不得给出数字
    for rf in result.formulas:
        for ref in rf.refs:
            assert ref.number is None
            assert ref.error_code == "ref_cycle"


def test_three_node_cycle_detected_but_dag_references_still_resolve():
    result = resolve([
        f("A", r"\ref{c} \label{a}"),
        f("B", r"\ref{a} \label{b}"),
        f("C", r"\ref{b} \label{c}"),
        f("D", r"\ref{a} \label{d}"),
    ])
    assert any(e.code == "ref_cycle" for e in result.errors)
    # D 不在环上，它对 a 的引用仍必须正常解析
    d = next(x for x in result.formulas if x.id == "D")
    assert d.refs[0].number == 1


def test_label_declared_in_metadata_field():
    result = resolve([f("a", "x=y", label="meta")])
    assert result.label_to_number == {"meta": 1}
    assert result.formulas[0].label == "meta"


def test_extract_helpers_ignore_braces_in_label_name():
    labels = extract_labels(r"\label{one} and \label{two}")
    assert [l[0] for l in labels] == ["one", "two"]
    refs = extract_refs(r"\ref{one} and \eqref{two}")
    assert [(r[0], r[1]) for r in refs] == [("ref", "one"), ("eqref", "two")]


def test_labels_are_stripped_from_rendered_source():
    result = resolve([f("a", r"x \label{k} = y")])
    assert r"\label" not in result.formulas[0].rendered_source
