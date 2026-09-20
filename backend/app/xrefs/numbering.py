"""交叉引用内核：标签解析、顺序编号、引用解析与三类异常检测。

这是必须在后端完成、可被独立验证的核心逻辑，不依赖任何前端状态。

公开入口：``resolve(formulas, base=1)``

编号规则（刻意简单、确定，可独立验证）：
- 公式编号只由它在列表中的位置决定：``base + index``；
- 标签 -> 公式 的绑定由标签声明唯一决定，与编号是两件事；
- 因此拖动顺序后重新调用本函数，所有编号与所有 \\ref 显示必然同步更新。

检测的三类异常（一律报错，绝不静默渲染错号）：
1. ``duplicate_label``：同一标签被多个公式声明；
2. ``undefined_label``：\\ref/\\eqref 指向不存在的标签；
3. ``ref_cycle``：引用图成环（A 引用 B、B 又引用 A 这类相互依赖）。
异常引用在渲染源码中统一替换为醒目的 ``\\boxed{?}`` 占位。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# 匹配 \label{...} / \ref{...} / \eqref{...}，大括号内不允许出现未转义的 }
_LABEL_RE = re.compile(r"\\label\s*\{([^{}]*)\}")
_REF_RE = re.compile(r"\\(ref|eqref)\s*\{([^{}]*)\}")

REF_ERROR_CODES = frozenset({"undefined_label", "duplicate_label_target",
                             "ref_cycle"})


@dataclass
class XRefError:
    code: str
    message: str
    formula_id: str
    offset: int          # 在该公式源码内的字符偏移（行/列由调用方换算）
    line: int
    column: int
    label: str | None = None
    end_offset: int | None = None

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "formula_id": self.formula_id,
            "offset": self.offset,
            "line": self.line,
            "column": self.column,
            "label": self.label,
            "end_offset": self.end_offset,
        }


@dataclass
class RefResolution:
    formula_id: str
    label: str
    raw: str                  # 原始 \ref{...} 文本
    start: int
    end: int
    number: int | None        # 解析出的编号；异常时为 None
    kind: str                 # 'ref' | 'eqref'
    error_code: str | None = None

    def to_dict(self) -> dict:
        return {
            "formula_id": self.formula_id,
            "label": self.label,
            "raw": self.raw,
            "start": self.start,
            "end": self.end,
            "number": self.number,
            "kind": self.kind,
            "error_code": self.error_code,
        }


@dataclass
class ResolvedFormula:
    id: str
    number: int
    label: str | None
    source: str               # 原始源码
    rendered_source: str      # 去掉 \label、替换 \ref 后的源码
    refs: list[RefResolution] = field(default_factory=list)
    has_error: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "number": self.number,
            "label": self.label,
            "source": self.source,
            "rendered_source": self.rendered_source,
            "refs": [r.to_dict() for r in self.refs],
            "has_error": self.has_error,
        }


@dataclass
class ResolveResult:
    formulas: list[ResolvedFormula]
    label_to_number: dict[str, int]
    errors: list[XRefError]

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "formulas": [f.to_dict() for f in self.formulas],
            "label_to_number": self.label_to_number,
            "errors": [e.to_dict() for e in self.errors],
        }


def _line_col(source: str, pos: int) -> tuple[int, int]:
    line, col = 1, 1
    for i, ch in enumerate(source):
        if i >= pos:
            break
        if ch == "\n":
            line += 1
            col = 1
        else:
            col += 1
    return line, col


def extract_labels(source: str) -> list[tuple[str, int, int]]:
    """返回源码内全部 ``\\label{name}``：[(name, start, end), ...]。"""
    return [(m.group(1).strip(), m.start(), m.end())
            for m in _LABEL_RE.finditer(source)]


def extract_refs(source: str) -> list[tuple[str, str, int, int]]:
    """返回源码内全部引用：[(kind, label, start, end), ...]。"""
    return [(m.group(1), m.group(2).strip(), m.start(), m.end())
            for m in _REF_RE.finditer(source)]


def _tarjan_cycles(graph: dict[str, set[str]]) -> list[set[str]]:
    """在引用图上求 SCC，返回节点数 > 1 的强连通分量（即环）。"""
    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    cycles: list[set[str]] = []

    sys_nodes = list(graph)

    def strongconnect(v: str) -> None:
        nonlocal index
        indices[v] = index
        lowlink[v] = index
        index += 1
        stack.append(v)
        on_stack.add(v)
        for w in graph.get(v, ()):  # 只沿“目标也在图中”的边走
            if w not in graph:
                continue
            if w not in indices:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in on_stack:
                lowlink[v] = min(lowlink[v], indices[w])
        if lowlink[v] == indices[v]:
            comp: set[str] = set()
            while True:
                w = stack.pop()
                on_stack.discard(w)
                comp.add(w)
                if w == v:
                    break
            # 单节点成环需要自引用边
            if len(comp) > 1 or v in graph.get(v, set()):
                cycles.append(comp)

    for node in sys_nodes:
        if node not in indices:
            strongconnect(node)
    return cycles


def resolve(formulas: list[dict], base: int = 1) -> ResolveResult:
    """解析整份工作区的编号与交叉引用。

    参数：
        formulas: [{"id": str, "source": str, "label": str | None}]，顺序即显示顺序。
        base: 起始编号（默认 1）。

    返回 :class:`ResolveResult`，其中 label_to_number、每个公式的
    number/rendered_source/refs 与 errors 均可直接断言。
    """
    errors: list[XRefError] = []

    # 1. 编号（仅取决于位置）
    numbers = {f["id"]: base + pos for pos, f in enumerate(formulas)}

    # 2. 标签声明：显式 label 字段 + 源码内 \label 合并，重复即报错
    #    owner[label] = 第一个声明者 id；再次声明 -> duplicate_label
    owner: dict[str, str] = {}
    duplicate_labels: set[str] = set()

    def declare(fid: str, label: str, start: int, end: int) -> None:
        label = label.strip()
        if not label:
            return
        if label not in owner:
            owner[label] = fid
        elif owner[label] != fid:
            duplicate_labels.add(label)
            src = next(s for s in formulas if s["id"] == fid)["source"]
            ln, col = _line_col(src, start)
            first_owner = owner[label]
            errors.append(XRefError(
                "duplicate_label",
                f"标签 {label!r} 重复：公式 {numbers[fid]} 与公式 "
                f"{numbers[first_owner]} 声明了同一个标签，"
                "标签必须在整个工作区唯一",
                fid, start, ln, col, label=label, end_offset=end))
        elif start != 0 or end != 0:
            # 同一公式既通过元数据又通过源码 \label 声明了同一标签：冗余但合法，
            # 仅当它与别的声明者冲突时才在上面报错。
            pass

    for f in formulas:
        fid = f["id"]
        source = f.get("source", "")
        if f.get("label"):
            # 显式标签属于元数据，错误定位到公式源码开头
            declare(fid, f["label"], 0, 0)
        for name, start, end in extract_labels(source):
            declare(fid, name, start, end)

    label_to_number: dict[str, int] = {}
    for label, fid in owner.items():
        if label in duplicate_labels:
            continue
        label_to_number[label] = numbers[fid]

    # 3. 收集引用，建引用图（公式 -> 它引用到的公式集合）
    raw_refs: dict[str, list[tuple[str, str, int, int]]] = {}
    fid_by_label = {label: fid for label, fid in owner.items()}
    graph: dict[str, set[str]] = {f["id"]: set() for f in formulas}
    for f in formulas:
        fid = f["id"]
        refs = extract_refs(f.get("source", ""))
        raw_refs[fid] = refs
        for _kind, label, _s, _e in refs:
            target = fid_by_label.get(label)
            if target is not None and target != fid:
                graph[fid].add(target)
            elif target == fid:
                graph[fid].add(fid)  # 自环

    # 4. 成环检测
    cycle_components = _tarjan_cycles(graph)
    cyclic_fids: set[str] = set()
    for comp in cycle_components:
        cyclic_fids |= comp
    for comp in cycle_components:
        members = sorted(numbers[x] for x in comp)
        for fid in comp:
            src = next(s for s in formulas if s["id"] == fid)["source"]
            # 把错误挂到该公式参与成环的引用上
            for kind, label, start, end in raw_refs[fid]:
                target = fid_by_label.get(label)
                if target in comp:
                    ln, col = _line_col(src, start)
                    errors.append(XRefError(
                        "ref_cycle",
                        f"交叉引用成环：公式 {numbers[fid]} 通过 {label!r} "
                        f"引用公式 {numbers[target]}，但它们相互引用形成环"
                        f"（环内公式编号：{members}），无法给出无歧义的编号依赖",
                        fid, start, ln, col, label=label, end_offset=end))

    # 5. 逐条引用解析 + 构造渲染源码
    resolved: list[ResolvedFormula] = []
    for f in formulas:
        fid = f["id"]
        source = f.get("source", "")
        number = numbers[fid]
        # 该公式生效的标签：优先元数据 label，其次源码内第一个有效 \label
        label_value = f.get("label")
        if not label_value:
            ins = extract_labels(source)
            if ins:
                cand = ins[0][0]
                if owner.get(cand) == fid and cand not in duplicate_labels:
                    label_value = cand
        refs_out: list[RefResolution] = []
        # 从后往前替换，避免偏移失效
        pieces = source
        replacements: list[tuple[int, int, str, RefResolution]] = []
        for kind, label, start, end in raw_refs[fid]:
            target = fid_by_label.get(label)
            err_code: str | None = None
            num: int | None = None
            if target is None:
                err_code = "undefined_label"
            elif label in duplicate_labels:
                err_code = "duplicate_label_target"
            elif fid in cyclic_fids and target in cyclic_fids and \
                    _same_cycle(fid, target, cycle_components):
                err_code = "ref_cycle"
            else:
                num = numbers[target]
            res = RefResolution(fid, label, source[start:end], start, end,
                                num, kind, err_code)
            refs_out.append(res)
            if err_code is not None:
                ln, col = _line_col(source, start)
                if err_code == "undefined_label":
                    errors.append(XRefError(
                        "undefined_label",
                        f"引用了不存在的标签 {label!r}"
                        f"（公式 {number}，第 {ln} 行第 {col} 列）："
                        f"工作区中没有任何公式声明该标签",
                        fid, start, ln, col, label=label, end_offset=end))
                elif err_code == "duplicate_label_target":
                    errors.append(XRefError(
                        "duplicate_label_target",
                        f"引用的标签 {label!r} 被多个公式重复声明，"
                        f"无法确定指向哪个编号（公式 {number}）",
                        fid, start, ln, col, label=label, end_offset=end))
                # ref_cycle 已在上一步报过，不重复
                replacement = r"\boxed{?}"
            else:
                replacement = str(num) if kind == "ref" else f"({num})"
            replacements.append((start, end, replacement, res))

        rendered = source
        for start, end, text, _res in sorted(replacements,
                                             key=lambda x: x[0], reverse=True):
            rendered = rendered[:start] + text + rendered[end:]
        # 去掉所有 \label{...}
        rendered = _LABEL_RE.sub("", rendered)

        has_error = any(r.error_code for r in refs_out)
        resolved.append(ResolvedFormula(
            id=fid, number=number, label=label_value,
            source=source, rendered_source=rendered,
            refs=sorted(refs_out, key=lambda r: r.start),
            has_error=has_error))

    return ResolveResult(formulas=resolved,
                         label_to_number=label_to_number, errors=errors)


def _same_cycle(a: str, b: str, components: list[set[str]]) -> bool:
    return any(a in comp and b in comp for comp in components)
