"""矩阵/环境结构化渲染测试。"""
from __future__ import annotations

import pytest

pytest.importorskip("matplotlib")

from app.render.matrices import (find_top_environments,  # noqa: E402
                                 split_cells)
from app.render.renderer import render_piece  # noqa: E402


def test_find_top_level_environment():
    src = r"a + \begin{pmatrix}1&0\\0&1\end{pmatrix} + b"
    blocks = find_top_environments(src)
    assert len(blocks) == 1
    b = blocks[0]
    assert b["env"] == "pmatrix"
    assert src[b["body_start"]:b["body_end"]] == r"1&0\\0&1"


def test_nested_environment_block_is_balanced():
    # 外层 aligned 必须作为一个完整块被识别（其 \end 正确匹配，
    # 不会被内部的 cases 环境干扰）；嵌套 cases 在单元格渲染阶段处理。
    src = (r"\begin{aligned} a &= \begin{cases} x \\ y \end{cases} \\ "
           r"b &= 2 \end{aligned}")
    blocks = find_top_environments(src)
    assert len(blocks) == 1
    top = blocks[0]
    assert top["env"] == "aligned"
    body = src[top["body_start"]:top["body_end"]]
    assert r"\begin{cases}" in body and r"\end{cases}" in body


def test_multile_top_level_environments_found():
    src = (r"\begin{pmatrix} a \\ b \end{pmatrix}"
           r" + \begin{cases} x \\ y \end{cases}")
    blocks = find_top_environments(src)
    assert [b["env"] for b in blocks] == ["pmatrix", "cases"]


def test_unmatched_environment_not_reported_as_block():
    assert find_top_environments(r"\begin{matrix} a & b") == []


def test_split_matrix_into_rows_and_cells():
    rows = split_cells(r"1&0\\0&1", "pmatrix")
    assert rows == [["1", "0"], ["0", "1"]]


def test_split_cases_single_column():
    rows = split_cells(r" x + y = 1 \\ 2x - y = 0 ", "cases")
    assert rows == [["x + y = 1"], ["2x - y = 0"]]


def test_array_column_spec_stripped_only_for_array():
    rows = split_cells(r"{cc} a & b \\ c & d", "array")
    assert rows[0] == ["a", "b"]
    # 非 array 环境不应吃掉首个平衡组
    rows2 = split_cells(r"{a} & b", "pmatrix")
    assert rows2 == [["{a}", "b"]]


def test_rendered_matrix_has_grid_and_delimiters():
    html = render_piece(r"\begin{bmatrix} a & b \\ c & d \end{bmatrix}")
    assert "env-bmatrix" in html
    assert html.count("env-cell") == 4
    # 左右方括号定界符
    assert "[" in html and "]" in html


def test_rendered_alignment_keeps_equations_inline():
    html = render_piece(
        r"f = \begin{aligned} x &= 1 \\ y &= 2 \end{aligned} + c")
    assert "env-aligned" in html
    # 外部的 f = 与 + c 至少渲染成图片
    assert html.count("tex-img") >= 2
