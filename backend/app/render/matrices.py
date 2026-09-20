"""矩阵/对齐/cases 环境的结构化渲染。

matplotlib mathtext 不支持 ``\\begin{matrix}`` 这类环境，但支持单元格内部的
任意数学排版。因此这里：
1. 在源码中找出 *花括号深度为 0* 的完整 ``\\begin{env}...\\end{env}`` 块；
2. 单元格内容仍交给 mathtext 渲染（保证分式、根号等内部排版正确）；
3. 外层用 HTML 网格摆放行列，并为 pmatrix/bmatrix/vmatrix 等绘制定界符。

环境之外的文本由调用方按普通数学片段渲染。
"""
from __future__ import annotations

import html
import re

_BEGIN_RE = re.compile(r"\\begin\s*\{([^}]*)\*?\}")
_END_RE_TEMPLATE = r"\\end\s*\{%s\*?\}"

MATRIX_ENVS = {
    "matrix", "pmatrix", "bmatrix", "Bmatrix", "vmatrix", "Vmatrix",
    "smallmatrix", "array", "cases", "aligned", "align", "gathered",
    "gather", "split", "eqnarray", "multline", "alignedat",
    "subarray", "subarray*",
}

# 环境 -> 左右定界符样式
_DELIMITERS = {
    "matrix": ("", ""),
    "pmatrix": ("(", ")"),
    "bmatrix": ("[", "]"),
    "Bmatrix": ("{", "}"),
    "vmatrix": ("|", "|"),
    "Vmatrix": ("‖", "‖"),
    "smallmatrix": ("", ""),
    "array": ("", ""),
    "cases": ("{", ""),
    "aligned": ("", ""),
    "align": ("", ""),
    "gathered": ("", ""),
    "gather": ("", ""),
    "split": ("", ""),
    "eqnarray": ("", ""),
    "multline": ("", ""),
    "alignedat": ("", ""),
}


def find_top_environments(source: str) -> list[dict]:
    """找出所有花括号深度为 0 的完整环境块。

    返回 [{"env", "start", "end", "body_start", "body_end", "columns"}]，
    按 start 升序；不配对的 \begin 不出现在结果中（交给容错/错误路径）。
    """
    results: list[dict] = []
    depth = 0
    i = 0
    n = len(source)
    while i < n:
        ch = source[i]
        if ch == "\\":
            m = _BEGIN_RE.match(source, i)
            if m and depth == 0:
                env = m.group(1).strip().rstrip("*")
                end_re = re.compile(_END_RE_TEMPLATE % re.escape(env))
                em = end_re.search(source, m.end())
                if em:
                    # 同一环境内允许嵌套同名/其它环境：用深度扫描更稳妥，
                    # 这里通过逐层配对 \begin/\end 找匹配
                    body_start = m.end()
                    body_end, close_end = _match_env_end(source, body_start, env)
                    if body_end is not None:
                        results.append({
                            "env": env,
                            "start": i,
                            "end": close_end,
                            "body_start": body_start,
                            "body_end": body_end,
                        })
                        i = close_end
                        continue
            # 跳过反斜杠命令，避免把命令名里的 { 计入深度
            j = i + 1
            if j < n and source[j].isalpha():
                while j < n and source[j].isalpha():
                    j += 1
            else:
                j = i + 2
            i = j
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(0, depth - 1)
        i += 1
    return results


def _match_env_end(source: str, pos: int, env: str):
    """从 body 起点找同名环境的匹配 \\end，返回 (body_end, close_end) 或 (None, None)。"""
    begin_re = re.compile(r"\\begin\s*\{([^}]*?)\*?\}")
    end_re = re.compile(r"\\end\s*\{([^}]*?)\*?\}")
    depth = 1
    i = pos
    while i < len(source):
        mb = begin_re.search(source, i)
        me = end_re.search(source, i)
        nxt = mb if (mb and (not me or mb.start() < me.start())) else me
        if nxt is None:
            return None, None
        name = nxt.group(1).strip().rstrip("*")
        if nxt is mb:
            depth += 1
        else:
            depth -= 1
            if depth == 0 and name == env:
                return nxt.start(), nxt.end()
        i = nxt.end()
    return None, None


def split_cells(body: str, env: str = "matrix") -> list[list[str]]:
    r"""把环境体切成 rows -> cells。行分隔为 ``\\``，列分隔为 ``&``。

    花括号深度 > 0 时不切分。array 环境开头的列格式 ``{ccc}`` 会被忽略。
    """
    # 仅 array/alignedat 在环境体开头带 {cc|c} 列格式说明
    if env in ("array", "alignedat"):
        body = re.sub(r"^\s*\{[^}]*\}\s*", "", body, count=1)
    rows: list[list[str]] = []
    cells: list[str] = []
    buf: list[str] = []
    depth = 0
    i = 0
    n = len(body)

    def end_cell() -> None:
        cells.append("".join(buf).strip())
        buf.clear()

    def end_row() -> None:
        end_cell()
        # 必须追加副本：cells 随后会被 clear 复用
        rows.append(list(cells))
        cells.clear()

    while i < n:
        ch = body[i]
        if ch == "{":
            depth += 1
            buf.append(ch)
            i += 1
            continue
        if ch == "}":
            depth = max(0, depth - 1)
            buf.append(ch)
            i += 1
            continue
        if depth == 0:
            # 行分隔 \\
            if ch == "\\" and i + 1 < n and body[i + 1] == "\\":
                end_row()
                i += 2
                continue
            if ch == "&":
                end_cell()
                i += 1
                continue
        buf.append(ch)
        i += 1
    if buf or cells:
        end_row()
    # 规整列数
    width = max((len(r) for r in rows), default=1)
    for r in rows:
        while len(r) < width:
            r.append("")
    return rows


def delimiter_html(symbol: str, side: str) -> str:
    if not symbol:
        return ""
    cls = "env-delim"
    if symbol in ("|", "‖"):
        border = "border-left" if side == "left" else "border-right"
        return (f'<span class="{cls} env-delim-line" '
                f'style="{border}:2px solid currentColor"></span>')
    return f'<span class="{cls}">{html.escape(symbol)}</span>'
