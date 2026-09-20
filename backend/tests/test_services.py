"""服务编排层端到端测试：一次 analyze 同时覆盖编号、结构与容错渲染。"""
from __future__ import annotations

import pytest

pytest.importorskip("matplotlib")

from app.services import analyze_formulas  # noqa: E402


def test_analyze_reorder_and_render():
    formulas = [
        {"id": "A", "source": r"\ref{planck} derives", "label": None},
        {"id": "B", "source": r"E=\hbar\omega \label{planck}", "label": None},
    ]
    result = analyze_formulas(formulas)
    assert result["ok"]
    assert result["label_to_number"] == {"planck": 2}

    reversed_result = analyze_formulas(list(reversed(formulas)))
    assert reversed_result["label_to_number"] == {"planck": 1}
    a = next(f for f in reversed_result["formulas"] if f["id"] == "A")
    assert a["number"] == 2
    assert a["rendered_source"] == "1 derives"
    assert "tex-img" in a["render"]["html"]


def test_analyze_reports_structure_error_and_tolerant_html():
    formulas = [{"id": "a",
                 "source": r"x = \frac{1}{2} + \\sqrt{y", "label": None}]
    result = analyze_formulas(formulas, tolerant=True)
    assert result["ok"] is False
    f0 = result["formulas"][0]
    assert any(e["code"] == "missing_rbrace"
               for e in f0["structure"]["errors"])
    # 容错渲染仍然产出可显示内容，不是白屏
    assert "tex-img" in f0["render"]["html"]


def test_analyze_undefined_ref_surfaces_in_xref_errors():
    result = analyze_formulas([
        {"id": "a", "source": r"\ref{nope}", "label": None}
    ])
    assert any(e["code"] == "undefined_label"
               for e in result["xref_errors"])
