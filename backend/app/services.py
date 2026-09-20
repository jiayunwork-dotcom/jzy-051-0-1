"""编排层：把结构解析、交叉引用编号、后端渲染组合成一次“分析”操作。

/api/analyze 的所有正确性判断都在这里汇总，路由层只做序列化。
"""
from __future__ import annotations

from .parser.structure import check_structure
from .render.renderer import RenderError, render_strict, render_tolerant
from .xrefs.numbering import resolve


def analyze_formulas(formulas: list[dict], base: int = 1,
                     tolerant: bool = True, fontsize: int = 18) -> dict:
    """对一份工作区的全部公式做：编号/引用解析 → 结构检查 → 渲染。

    返回结构：
    {
      "ok": bool,                # 无任何错误（含结构与交叉引用）
      "label_to_number": {...},
      "formulas": [{
        "id", "number", "label", "source", "rendered_source",
        "structure": {"ok", "errors", "tokens"},
        "xref_errors": [...],
        "render": {"ok", "html", "segments", ...}
      }],
      "xref_errors": [...]       # 跨公式的交叉引用错误全集
    }
    """
    resolved = resolve(formulas, base=base)

    out_formulas: list[dict] = []
    for rf in resolved.formulas:
        # 结构检查针对用户正在编辑的原始源码，保证行列偏移与编辑器一致；
        # \ref{...}/\label{...} 本身也在必选参数校验名单内，畸形写法照样报。
        structure = check_structure(rf.source)
        xref_errors = [r.to_dict() for r in rf.refs if r.error_code]
        if tolerant:
            render = render_tolerant(rf.rendered_source, fontsize=fontsize)
        else:
            try:
                render = render_strict(rf.rendered_source, fontsize=fontsize)
            except RenderError as exc:
                render = {
                    "ok": False,
                    "html": (f'<span class="tex-formula">'
                             f'<span class="tex-error" title="{str(exc)}">'
                             f"渲染失败</span></span>"),
                    "svg": None,
                    "segments": [{
                        "text": rf.rendered_source, "kind": "math",
                        "ok": False, "html": None, "error": str(exc),
                    }],
                    "error": str(exc),
                }
        out_formulas.append({
            "id": rf.id,
            "number": rf.number,
            "label": rf.label,
            "source": rf.source,
            "rendered_source": rf.rendered_source,
            "structure": structure.to_dict(),
            "xref_errors": xref_errors,
            "render": render,
        })

    return {
        "ok": resolved.ok and all(
            f["structure"]["ok"] for f in out_formulas),
        "label_to_number": resolved.label_to_number,
        "formulas": out_formulas,
        "xref_errors": [e.to_dict() for e in resolved.errors],
    }
