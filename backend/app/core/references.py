"""Cross-reference resolution and formula renumbering.

This module is the authoritative backend kernel for everything related to
formula numbering and ``\\ref{label}``.  The frontend never computes a
number itself — it only displays what this module returns.

Pipeline
--------
1. Formulas are numbered by their **position in the list** (1-based).
   Reordering the list therefore automatically renumbers every formula;
   nothing is stored about numbers.
2. Every ``\\label`` value carried by a formula must be unique.  Duplicate
   labels are reported (``duplicate_label``) and references to an ambiguous
   label are not resolved to any number.
3. Each ``\\ref{label}`` is matched to the formula owning that label.
   Missing targets produce ``undefined_label`` issues with the precise
   source position of the reference.
4. The directed graph "formula A references formula B" is checked for
   cycles (self references included) using Tarjan's strongly connected
   components; each SCC of size >= 2 (plus self loops) yields one
   ``reference_cycle`` issue **per member formula**, including the cycle
   path so the report is actionable.

Numbers are always still computed (they depend only on order); cycles are
reported as issues but never silently change a displayed number.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .lexer import line_col
from .nodes import LabelNode, RefNode
from .parser import parse_source


@dataclass
class FormulaInput:
    client_id: str
    source: str = ""
    label: str | None = None


@dataclass
class RefOccurrence:
    label: str
    offset: int          # offset of the label text inside formula source
    line: int
    column: int
    target_id: str | None = None   # None when unresolved
    number: int | None = None      # resolved display number, if any


@dataclass
class RefIssue:
    code: str            # undefined_label | duplicate_label | reference_cycle
    message: str
    formula_id: str
    label: str | None = None
    offset: int | None = None
    line: int | None = None
    column: int | None = None
    cycle: list[str] | None = None

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "formulaId": self.formula_id,
            "label": self.label,
            "offset": self.offset,
            "line": self.line,
            "column": self.column,
            "cycle": self.cycle,
        }


@dataclass
class ResolvedFormula:
    client_id: str
    number: int
    label: str | None
    occurrences: list[RefOccurrence] = field(default_factory=list)

    @property
    def ref_numbers(self) -> dict[str, int]:
        """Label -> number for every *successfully* resolved occurrence."""
        out: dict[str, int] = {}
        for occ in self.occurrences:
            if occ.number is not None:
                out[occ.label] = occ.number
        return out


@dataclass
class Resolution:
    formulas: list[ResolvedFormula]
    issues: list[RefIssue]
    # label -> number, only for labels that are unique and usable
    number_by_label: dict[str, int]
    # formula id -> {label: number} for rendering that formula
    refs_for_render: dict[str, dict[str, int]]

    @property
    def ok(self) -> bool:
        return not self.issues


# ---------------------------------------------------------------------------
# Reference extraction
# ---------------------------------------------------------------------------


def _collect_refs(node, acc: list[RefNode]) -> None:
    _collect_nodes(node, acc, RefNode)


def extract_refs(source: str) -> list[RefNode]:
    """Return every ``\\ref{...}`` node in *source* (works despite parse
    errors — extraction is purely structural)."""
    result = parse_source(source).root
    refs: list[RefNode] = []
    _collect_refs(result, refs)
    return refs


def extract_labels(source: str) -> list[LabelNode]:
    """Return every ``\\label{...}`` node declared inside *source*."""
    result = parse_source(source).root
    labels: list[LabelNode] = []
    _collect_nodes(result, labels, LabelNode)
    return labels


def _collect_nodes(node, acc, cls) -> None:
    if isinstance(node, cls):
        acc.append(node)
    for child in getattr(node, "children", []) or []:
        _collect_nodes(child, acc, cls)
    for attr in ("numerator", "denominator", "upper", "lower", "radicand",
                 "degree", "child", "base", "sub", "sup"):
        val = getattr(node, attr, None)
        if val is not None and not isinstance(val, (str, int, list)):
            _collect_nodes(val, acc, cls)
    for row in getattr(node, "rows", []) or []:
        for cell in row:
            _collect_nodes(cell, acc, cls)


# ---------------------------------------------------------------------------
# Tarjan SCC
# ---------------------------------------------------------------------------


def _find_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    index: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    sccs: list[list[str]] = []
    counter = 0

    def strongconnect(v: str) -> None:
        nonlocal counter
        index[v] = lowlink[v] = counter
        counter += 1
        stack.append(v)
        on_stack.add(v)
        for w in graph.get(v, ()):  # successor
            if w not in index:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in on_stack:
                lowlink[v] = min(lowlink[v], index[w])
        if lowlink[v] == index[v]:
            comp: list[str] = []
            while True:
                w = stack.pop()
                on_stack.discard(w)
                comp.append(w)
                if w == v:
                    break
            sccs.append(comp)

    for v in graph:
        if v not in index:
            strongconnect(v)

    cycles: list[list[str]] = []
    for comp in sccs:
        if len(comp) > 1:
            cycles.append(comp)
        elif comp[0] in graph.get(comp[0], set()):
            cycles.append(comp)  # self-loop
    return cycles


# ---------------------------------------------------------------------------
# Main resolution
# ---------------------------------------------------------------------------


def resolve_formulas(formulas: list[FormulaInput]) -> Resolution:
    issues: list[RefIssue] = []

    # 1) Numbering is purely positional.
    numbers = {f.client_id: i + 1 for i, f in enumerate(formulas)}

    # 2) Collect labels from BOTH the explicit per-formula ``label`` field
    #    and inline ``\label{...}`` declarations in the source.  Declaring
    #    the same label twice on the SAME formula is harmless (idempotent);
    #    two DIFFERENT formulas sharing a label is a duplicate-label error.
    label_owners: dict[str, list[str]] = {}
    formula_labels: dict[str, list[str]] = {}
    for f in formulas:
        declared: list[str] = []
        if f.label:
            declared.append(f.label)
        for lab in extract_labels(f.source):
            declared.append(lab.label)
        # Preserve order, de-duplicate within this formula.
        formula_labels[f.client_id] = list(dict.fromkeys(declared))
        for label in formula_labels[f.client_id]:
            owners = label_owners.setdefault(label, [])
            if f.client_id not in owners:
                owners.append(f.client_id)

    unique_owner: dict[str, str] = {}
    for label, owners in label_owners.items():
        if len(owners) > 1:
            for owner in owners:
                issues.append(RefIssue(
                    code="duplicate_label",
                    message=(f"标签 “{label}” 被 {len(owners)} 个公式重复使用："
                             f"公式 {', '.join(str(numbers[o]) for o in owners)}，"
                             "每个标签必须唯一，否则交叉引用无法确定目标。"),
                    formula_id=owner,
                    label=label,
                ))
        else:
            unique_owner[label] = owners[0]

    # 3) Extract references, resolve each against unique labels.
    resolved: list[ResolvedFormula] = []
    graph: dict[str, set[str]] = {f.client_id: set() for f in formulas}

    for f in formulas:
        rf = ResolvedFormula(
            client_id=f.client_id, number=numbers[f.client_id],
            label=(formula_labels[f.client_id][0]
                   if formula_labels[f.client_id] else None))
        for ref in extract_refs(f.source):
            line, col = line_col(f.source, ref.label_start)
            occ = RefOccurrence(label=ref.label, offset=ref.label_start,
                                line=line, column=col)
            owner = unique_owner.get(ref.label)
            if owner is None:
                if ref.label in label_owners:
                    # Duplicated label: already reported on the owners, but
                    # the referencing site itself is also ambiguous.
                    issues.append(RefIssue(
                        code="undefined_label",
                        message=(f"引用 “{ref.label}” 指向的标签被多个公式"
                                 "重复声明，无法确定引用目标。"),
                        formula_id=f.client_id, label=ref.label,
                        offset=occ.offset, line=line, column=col))
                else:
                    issues.append(RefIssue(
                        code="undefined_label",
                        message=(f"引用了不存在的标签 “{ref.label}”："
                                 "请检查 \\ref{} 中的标签，或为目标公式添加"
                                 "该标签。"),
                        formula_id=f.client_id, label=ref.label,
                        offset=occ.offset, line=line, column=col))
            else:
                occ.target_id = owner
                occ.number = numbers[owner]
                graph[f.client_id].add(owner)
            rf.occurrences.append(occ)
        resolved.append(rf)

    # 4) Cycle detection on the dependency graph.
    for comp in _find_cycles(graph):
        member_set = set(comp)
        # Order the path by following graph edges within the SCC.
        path = _cycle_path(comp[0], graph, member_set)
        display = path if len(path) == 1 else path + [path[0]]
        for member in comp:
            issues.append(RefIssue(
                code="reference_cycle",
                message=("交叉引用成环：公式 "
                         + " → ".join(str(numbers[p]) for p in display)
                         + " 相互引用，标签依赖无法形成无环顺序。"),
                formula_id=member,
                cycle=path,
            ))

    number_by_label = {
        label: numbers[owner]
        for label, owner in unique_owner.items()
    }
    refs_for_render = {f.client_id: f.ref_numbers for f in resolved}

    return Resolution(formulas=resolved, issues=issues,
                      number_by_label=number_by_label,
                      refs_for_render=refs_for_render)


def _cycle_path(start: str, graph: dict[str, set[str]],
                members: set[str]) -> list[str]:
    """Return a readable cycle path starting at *start*.

    The list ends at the first successor already on the path (which equals
    *start* for a simple cycle); a self-loop is reported as just ``[start]``.
    """
    if start in graph.get(start, set()) and len(members) == 1:
        return [start]
    path = [start]
    current = start
    visited = {start}
    while True:
        nxt = next(iter(
            sorted(w for w in graph[current] if w in members and w not in
                   visited)), None)
        if nxt is None:
            return path
        path.append(nxt)
        visited.add(nxt)
        current = nxt


def renumber(formulas: list[FormulaInput]) -> list[int]:
    """Convenience: return the new number of each formula in list order.

    Reordering is just *passing the formulas in the new order* — numbers are
    never stored — so this is the single rule tests assert after a drag
    operation.
    """
    return [i + 1 for i, _ in enumerate(formulas)]
