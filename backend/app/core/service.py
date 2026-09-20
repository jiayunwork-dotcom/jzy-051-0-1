"""High-level formula service: the single entry point used by the API.

Combines the structural parser, spelling suggestions, tolerant renderer and
cross-reference kernel into plain-dict result objects, which doubles as the
documented input/output contract for automated tests.
"""

from __future__ import annotations

from .parser import parse_source
from .references import FormulaInput, resolve_formulas
from .renderer import render_mathml
from .tolerant import segments as _segments, render_segments


def parse_formula(source: str) -> dict:
    """Strict parse contract.

    Output::

        {
          "ok": bool,
          "errors": [ {code,message,offset,length,line,column,suggestion} ],
          "tree": "<opaque AST summary used only for debugging>"
        }
    """
    result = parse_source(source)
    return {
        "ok": result.ok,
        "errors": [e.as_dict() for e in result.errors],
    }


def render_formula(source: str, *, tolerant: bool = False,
                   refs: dict[str, int] | None = None) -> dict:
    """Render one formula.

    * strict mode (``tolerant=False``): any parse error means
      ``mathml`` is ``None`` and the caller must display ``errors``;
    * tolerant mode: ``mathml`` is always produced segment by segment;
      bad fragments are red ``<merror>`` markers, the rest still renders;
      ``segments`` lists the good/error/blank source spans explicitly.
    """
    result = parse_source(source)
    errors = [e.as_dict() for e in result.errors]
    ref_strings = {k: str(v) for k, v in (refs or {}).items()}

    if not tolerant:
        mathml = None if errors else render_mathml(
            result.root, source, ref_strings)
        return {"ok": result.ok, "errors": errors, "mathml": mathml,
                "segments": []}

    segs = [
        {"kind": s.kind, "start": s.start, "end": s.end, "text": s.text}
        for s in _segments(source, result.root, result.errors)
    ]
    mathml = render_segments(source, result.root, result.errors,
                             ref_strings)
    return {"ok": result.ok, "errors": errors, "mathml": mathml,
            "segments": segs}


def preview_workspace(formulas: list[dict], *,
                      tolerant: bool = True) -> dict:
    """Resolve numbering/references and render every formula.

    Input items: ``{"clientId": str, "source": str, "label": str|None}``.
    Output::

        {
          "ok": bool,                    # no parse & no reference issues
          "tolerant": bool,
          "formulas": [ {clientId,number,label,mathml,parseErrors,
                         references: [{label,line,column,number,resolved}]} ],
          "issues": [ {code,message,formulaId,label,line,column,cycle} ]
        }
    """
    inputs = [
        FormulaInput(client_id=f["clientId"], source=f.get("source", ""),
                     label=(f.get("label") or None))
        for f in formulas
    ]
    resolution = resolve_formulas(inputs)

    out_formulas = []
    all_ok = not resolution.issues
    for f, resolved in zip(inputs, resolution.formulas):
        refs = resolved.ref_numbers
        rendered = render_formula(f.source, tolerant=tolerant, refs=refs)
        if rendered["errors"]:
            all_ok = False
        out_formulas.append({
            "clientId": f.client_id,
            "number": resolved.number,
            "label": f.label,
            "mathml": rendered["mathml"],
            "parseErrors": rendered["errors"],
            "segments": rendered["segments"],
            "references": [
                {"label": o.label, "line": o.line, "column": o.column,
                 "number": o.number, "resolved": o.number is not None}
                for o in resolved.occurrences
            ],
        })

    return {
        "ok": all_ok,
        "tolerant": tolerant,
        "formulas": out_formulas,
        "issues": [i.as_dict() for i in resolution.issues],
    }
