"""容错渲染的切分器。

契约（可被自动化测试逐条覆盖）：
``segment_source(source)`` 把源码切成有序的 :class:`Segment` 列表：
- 每个 segment 是一段原文切片（kind 区分普通片段 / 空白）；
- 切分点只发生在 *花括号深度为 0* 的原子边界，因此一处局部错误
  不会吃掉与它不相邻的本可正确渲染的内容；
- 未闭合的花括号组按原文保留在它所属的最后一个片段中（渲染器负责修复），
  不会把后面的内容“卷”进错误片段。

渲染器对每个片段独立尝试渲染，失败的片段渲染为醒目占位标记。
"""
from __future__ import annotations

from dataclasses import dataclass

from .lexer import (ALIGN, CHAR, COMMAND, IGNORABLE, LBRACE, NEWLINE,
                    RBRACE, SPACE, SUB, SUP, tokenize)

# 在深度 0 处天然适合作为切分点的原子（关系/运算/对齐符号）
_SPLIT_TYPES = {SUP, SUB, ALIGN}
_SPLIT_VALUES = {"+", "-", "=", ",", ";", "|"}
MAX_CHUNK = 60  # 单片段目标上限（字符数）


@dataclass
class Segment:
    text: str
    start: int
    end: int
    kind: str = "math"          # 'math' | 'space'
    repaired: str | None = None  # 渲染器对该片段做修复后的内容（如有）

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "kind": self.kind,
            "repaired": self.repaired,
        }


def _command_span(tokens: list[Token], idx: int) -> int:
    """返回命令原子的结束 token 下标（并入紧随其后的平衡参数组）。"""
    j = idx + 1
    while True:
        k = j
        while k < len(tokens) and tokens[k].type in IGNORABLE:
            k += 1
        if k < len(tokens) and tokens[k].type == LBRACE:
            depth = 1
            m = k + 1
            while m < len(tokens):
                if tokens[m].type == LBRACE:
                    depth += 1
                elif tokens[m].type == RBRACE:
                    depth -= 1
                    if depth == 0:
                        m += 1
                        break
                m += 1
            j = m
            continue
        return j


def _emit_char_run(tokens: list[Token], start_idx: int,
                   out: list[tuple[int, int, str]]) -> int:
    """把从 start_idx 开始的连续普通字符（在遇到边界前）输出为一个 atom。"""
    j = start_idx
    while j < len(tokens):
        t = tokens[j]
        if (t.type in IGNORABLE or t.type in (LBRACE, RBRACE, COMMAND)
                or t.type in _SPLIT_TYPES
                or (t.type == CHAR and t.value in _SPLIT_VALUES)):
            break
        # 普通字符 token 内部若包含分隔字符（如 "x+y" 已被词法合并），仍切分
        if any(c in _SPLIT_VALUES for c in t.value):
            break
        j += 1
    if j == start_idx:
        j = start_idx + 1
    out.append((tokens[start_idx].start, tokens[j - 1].end, "atom"))
    return j


def _atoms(source: str) -> list[tuple[int, int, str]]:
    """返回有序原子列表 ``[(start, end, kind)]``，kind ∈ atom|space|split。

    切分保证（容错安全性的关键）：
    - 深度 0 的完整 ``{...}`` 组是一个 atom，内部不切；
    - 深度 0 的控制命令（连同其平衡参数组）是一个 atom；
    - 深度 0 的 ``+ - = , ; | & ^ _`` 是 split；
    - 连续空白是 space；
    - **未闭合组**：``{`` 到 EOF 的内容按 *组内相对深度 0* 继续切分，
      因此错误片段后面的 ``= z`` 这类本可独立渲染的内容不会被整段卷走。
    """
    tokens = tokenize(source)
    out: list[tuple[int, int, str]] = []
    idx = 0

    while idx < len(tokens):
        tok = tokens[idx]
        if tok.type in IGNORABLE:
            j = idx
            while j < len(tokens) and tokens[j].type in IGNORABLE:
                j += 1
            out.append((tok.start, tokens[j - 1].end, "space"))
            idx = j
            continue

        if tok.type in _SPLIT_TYPES or (tok.type == CHAR
                                       and tok.value in _SPLIT_VALUES):
            out.append((tok.start, tok.end, "split"))
            idx += 1
            continue

        if tok.type == LBRACE:
            depth = 1
            j = idx + 1
            while j < len(tokens):
                if tokens[j].type == LBRACE:
                    depth += 1
                elif tokens[j].type == RBRACE:
                    depth -= 1
                    if depth == 0:
                        j += 1
                        break
                j += 1
            if depth == 0:
                # 平衡组：整体作为一个 atom
                out.append((tok.start, tokens[j - 1].end, "atom"))
                idx = j
            else:
                # 未闭合组：{ 单独占位，组体按深度 1 为基准递归扫描
                out.append((tok.start, tok.end, "atom"))
                idx = _scan_unbalanced_body(tokens, idx + 1, 1, out)
            continue

        if tok.type == COMMAND:
            j = _command_span(tokens, idx)
            out.append((tok.start, tokens[j - 1].end, "atom"))
            idx = j
            continue

        idx = _emit_char_run(tokens, idx, out)

    return out


def _scan_unbalanced_body(tokens: list[Token], idx: int, base_depth: int,
                          out: list[tuple[int, int, str]]) -> int:
    """扫描未闭合组的组体（相对深度从 base_depth 起），在相对深度为 0 处切分。"""
    depth = base_depth
    while idx < len(tokens):
        tok = tokens[idx]
        if tok.type in IGNORABLE:
            j = idx
            while j < len(tokens) and tokens[j].type in IGNORABLE:
                j += 1
            out.append((tok.start, tokens[j - 1].end, "space"))
            idx = j
            continue
        if tok.type == LBRACE:
            # 嵌套（可能也是未闭合的）平衡组或未闭合组
            inner_depth = 1
            j = idx + 1
            while j < len(tokens):
                if tokens[j].type == LBRACE:
                    inner_depth += 1
                elif tokens[j].type == RBRACE:
                    inner_depth -= 1
                    if inner_depth == 0:
                        j += 1
                        break
                j += 1
            if inner_depth == 0:
                out.append((tok.start, tokens[j - 1].end, "atom"))
                idx = j
                continue
            out.append((tok.start, tok.end, "atom"))
            idx = _scan_unbalanced_body(tokens, idx + 1,
                                        depth + 1, out)
            continue
        if tok.type == RBRACE:
            depth -= 1
            if depth < base_depth:
                # 逻辑上不会发生（调用方已知未闭合），保险起见
                return idx + 1
            out.append((tok.start, tok.end, "atom"))
            idx += 1
            continue
        if tok.type in _SPLIT_TYPES or (tok.type == CHAR
                                       and tok.value in _SPLIT_VALUES):
            out.append((tok.start, tok.end, "split"))
            idx += 1
            continue
        if tok.type == COMMAND:
            j = _command_span(tokens, idx)
            out.append((tok.start, tokens[j - 1].end, "atom"))
            idx = j
            continue
        # 普通字符 run
        j = idx
        while j < len(tokens):
            t = tokens[j]
            if (t.type in IGNORABLE or t.type in (LBRACE, RBRACE, COMMAND)
                    or t.type in _SPLIT_TYPES
                    or (t.type == CHAR and t.value in _SPLIT_VALUES)):
                break
            j += 1
        if j == idx:
            j = idx + 1
        out.append((tokens[idx].start, tokens[j - 1].end, "atom"))
        idx = j
    return idx


def segment_source(source: str) -> list[Segment]:
    """把源码切为有序片段。空白也保留为独立片段，保证渲染间距自然。

    不变量（测试守死）：
    - 片段文本首尾相接拼回必然等于原文；
    - 每个片段的 ``source[start:end] == text``。
    """
    raw = _atoms(source)
    segments: list[Segment] = []

    def emit(s: int, e: int) -> None:
        if e <= s:
            return
        text = source[s:e]
        if text.strip() == "":
            segments.append(Segment(text=text, start=s, end=e, kind="space"))
            return
        lead = len(text) - len(text.lstrip())
        trail = len(text) - len(text.rstrip())
        if lead:
            segments.append(Segment(text=text[:lead], start=s,
                                    end=s + lead, kind="space"))
        segments.append(Segment(text=text.strip(), start=s + lead,
                                end=e - trail, kind="math"))
        if trail:
            segments.append(Segment(text=text[e - s - trail:],
                                    start=e - trail, end=e, kind="space"))

    chunk_start: int | None = None
    chunk_end: int | None = None
    for start, end, kind in raw:
        if kind == "space":
            if chunk_start is not None:
                emit(chunk_start, chunk_end)
                chunk_start = chunk_end = None
            emit(start, end)
            continue
        if kind == "split":
            if chunk_start is not None:
                emit(chunk_start, chunk_end)
                chunk_start = chunk_end = None
            emit(start, end)
            continue
        # atom：仅当与当前缓冲在原文中严格相邻且不超长时才并入
        text = source[start:end]
        if (chunk_start is not None and chunk_end == start
                and (chunk_end - chunk_start) + (end - start) <= MAX_CHUNK):
            chunk_end = end
        else:
            if chunk_start is not None:
                emit(chunk_start, chunk_end)
            chunk_start, chunk_end = start, end
        # 成组原子之后允许自然断片
        if "{" in text and end - start >= 2:
            # 平衡组整体保留（已并入），但若刚开新组就结束，同样可在下一原子断开
            pass
    if chunk_start is not None:
        emit(chunk_start, chunk_end)
    return segments


def repair_unbalanced(source: str) -> tuple[str, int]:
    """为未闭合花括号补 ``}``，返回 (修复后文本, 补入个数)。

    修复策略刻意保守：只在源码末尾补与缺失数量相等的右花括号。
    """
    depth = 0
    for ch in source:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(0, depth - 1)
    if depth == 0:
        return source, 0
    return source + ("}" * depth), depth
