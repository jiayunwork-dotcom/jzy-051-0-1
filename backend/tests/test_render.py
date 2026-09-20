"""后端渲染器测试（matplotlib mathtext）。

本地没有 matplotlib 时自动跳过；Docker 构建产物中必定安装，CI/容器内会执行。
"""
from __future__ import annotations

import pytest

matplotlib = pytest.importorskip("matplotlib")

from app.parser.tolerant import segment_source  # noqa: E402
from app.render.preprocess import preprocess  # noqa: E402
from app.render.renderer import (RenderError, render_piece, render_strict,  # noqa: E402
                                 render_tex, render_tolerant)


def test_preprocess_wraps_and_renames():
    out = preprocess(r"\dfrac{a}{b}")
    assert out.startswith("$") and out.endswith("$")
    assert r"\dfrac" not in out
    assert r"\frac" in out


def test_preprocess_strips_label_and_comments():
    out = preprocess(r"x=y \label{eq1} % note")
    assert r"\label" not in out
    assert "note" not in out


def test_preprocess_align_environment_mapped():
    out = preprocess(r"\begin{aligned} a &= 1 \\ b &= 2 \end{aligned}")
    assert "aligned" not in out
    assert "matrix" in out


def test_render_valid_formula_produces_svg():
    out = render_tex(r"$\frac{a}{b} + \sqrt{x}$")
    assert out["svg"].lstrip().startswith("<?xml")
    assert "data:image/svg+xml;base64" in out["html"]
    assert out["width_px"] > 0


def test_render_strict_failure_raises_render_error():
    with pytest.raises(RenderError):
        render_strict(r"\totallyunknowncmdXYZ")


def test_tolerant_renders_good_parts_despite_local_error():
    # 已知可渲染的片段 + 无法渲染的命令，容错下好片段不能被吃掉
    result = render_tolerant(r"x^2 + \totallyunknowncmdXYZ")
    assert result["ok"] is True
    html = result["html"]
    # 至少有一个成功片段渲染成图片
    assert html.count("tex-img") >= 1
    # 错误片段以醒目占位存在
    assert "tex-error" in html
    assert "totallyunknowncmdXYZ" in html


def test_tolerant_unclosed_brace_still_renders_something():
    result = render_tolerant(r"\frac{1}{2} + \sqrt{x")
    # 前半段必须成功渲染
    assert result["ok"] is True
    assert result["html"].count("tex-img") >= 1


def test_tolerant_independent_segments_render_independently():
    # 三段顶级内容，中间一段损坏：首尾两段仍应是成功图片
    result = render_tolerant(r"a + \totallyunknowncmdXYZ + b")
    ok_segments = [s for s in result["segments"]
                   if s.get("kind") == "math" and s.get("ok")]
    assert len(ok_segments) >= 2
    bad = [s for s in result["segments"] if s.get("ok") is False]
    assert bad and "totallyunknowncmdXYZ" in bad[0]["text"]


def test_render_greek_and_matrix():
    # 希腊字母走 mathtext；矩阵环境由结构化网格渲染
    assert "tex-img" in render_tex(r"$\alpha + \beta$")["html"]
    html = render_piece(r"\alpha + \begin{pmatrix}1&0\\0&1\end{pmatrix}")
    assert "env-matrix" in html
    assert html.count("env-cell") == 4
    cases = render_piece(
        r"\begin{cases} x + y = 1 \\ 2x - y = 0 \end{cases}")
    assert "env-cases" in cases
    assert cases.count("env-cell") == 2  # cases 是 2 行 1 列


def test_cjk_prose_renders_outside_mathtext():
    # 中日韩文字不应进入 mathtext（否则缺字方框），而应作为 prose 文本
    html = render_piece(r"由式 \eqref{x} 可得以下结论")
    # \eqref 在渲染阶段未做编号替换（编号在 numbering 层完成），
    # 这里只断言中文被分离为 prose，且数学部分仍产出图片
    assert "tex-prose" in html
    assert "由式" in html and "可得以下结论" in html
    assert "tex-img" in html
