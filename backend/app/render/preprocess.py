"""把通用 LaTeX 数学写法预处理为 matplotlib mathtext 可接受的子集。

纯字符串级变换，规则都是确定性的；无法识别的命令原样保留（交给渲染失败路径，
再由容错渲染处理），不在这里静默删除语义。
"""
from __future__ import annotations

import re

# 对齐/矩阵环境 -> mathtext 环境
_MATRIX_ENVS = {
    "matrix", "pmatrix", "bmatrix", "Bmatrix", "vmatrix", "Vmatrix",
    "smallmatrix",
}
_ALIGN_ENVS = {
    "aligned", "align", "align*", "gathered", "gather", "gather*",
    "eqnarray", "eqnarray*", "multline", "multline*",
}

_RENAME_CMDS = {
    r"\arcsin": r"\sin^{-1}",  # 不直接支持的反函数保守处理（下面再覆写为文本）
    r"\arccos": r"\cos^{-1}",
    r"\arctan": r"\tan^{-1}",
    r"\bmod": r"\bmod",
}

# mathtext 不认识、但有直接等价替换的命令（值为替换文本）
_REPLACE_CMDS = {
    r"\dfrac": r"\frac",
    r"\tfrac": r"\frac",
    r"\dbinom": r"\binom",
    r"\tbinom": r"\binom",
    r"\bm": r"\mathbf",
    r"\boldsymbol": r"\mathbf",
    r"\operatorname": r"\mathrm",
    r"\operatornamewithlimits": r"\mathrm",
    r"\text": r"\mathrm",
    r"\textrm": r"\mathrm",
    r"\textbf": r"\mathbf",
    r"\textit": r"\mathit",
    r"\textsf": r"\mathsf",
    r"\texttt": r"\mathtt",
    r"\dotsb": r"\cdots",
    r"\dotsm": r"\cdots",
    r"\dotsc": r"\ldots",
    r"\dotsi": r"\cdots",
    r"\not\in": r"\notin",
    r"\le ": r"\leq ",
    r"\ge ": r"\geq ",
    r"\ne ": r"\neq ",
    r"\to": r"\rightarrow",
    r"\gets": r"\leftarrow",
    r"\implies": r"\Rightarrow",
    r"\iff": r"\Leftrightarrow",
    r"\degree": r"^{\circ}",
    r"\colon": r":",
    r"\colon ": r": ",
    r"\brace": r"\}",
}

# 无参数、直接丢弃的样式/间距控制命令
# 注意：\\ 是矩阵/环境的换行符，绝不能在这里删除（只在环境外删除，见 _drop_cmds）
_DROP_CMDS = [
    r"\displaystyle", r"\textstyle", r"\scriptstyle", r"\scriptscriptstyle",
    r"\limits", r"\nolimits", r"\nonumber", r"\notag",
    r"\!", r"\,", r"\;", r"\:",
]

# 形如 \text{...} 这类在 mathtext 里不需要的包裹命令 -> 保留花括号内容
_UNWRAP_ENVS = {
    r"\hbox", r"\mbox", r"\vbox",
}

_ENV_BEGIN_RE = re.compile(r"\\begin\s*\{([^}]*)\}")
_ENV_END_RE = re.compile(r"\\end\s*\{([^}]*)\}")
_CMD_RE = re.compile(r"\\[a-zA-Z]+|\S|\\")


def _strip_comments(source: str) -> str:
    out: list[str] = []
    for line in source.splitlines(keepends=True):
        pct = line.find("%")
        if pct != -1:
            line = line[:pct] + ("\n" if line.endswith("\n") else "")
        out.append(line)
    return "".join(out)


def _convert_envs(source: str) -> str:
    def repl_begin(m: re.Match) -> str:
        name = m.group(1).strip()
        star = name.endswith("*")
        core = name[:-1] if star else name
        if core in _ALIGN_ENVS:
            return r"\begin{matrix}"
        if core == "array":
            return r"\begin{matrix}"
        if core in _MATRIX_ENVS:
            return m.group(0).replace(name, core)
        if core == "cases":
            return m.group(0)
        if core in ("split", "alignedat"):
            return r"\begin{matrix}"
        return m.group(0)

    def repl_end(m: re.Match) -> str:
        name = m.group(1).strip()
        star = name.endswith("*")
        core = name[:-1] if star else name
        if core in _ALIGN_ENVS or core == "array" or core in ("split", "alignedat"):
            return r"\end{matrix}"
        return m.group(0)

    source = _ENV_BEGIN_RE.sub(repl_begin, source)
    source = _ENV_END_RE.sub(repl_end, source)
    return source


def _drop_tag(source: str) -> str:
    # \tag{...} / \tag*{...} 不参与渲染
    source = re.sub(r"\\tag\*?\s*\{[^{}]*\}", "", source)
    return source


def _unwrap_cmds(source: str) -> str:
    for cmd in _UNWRAP_ENVS:
        # \hbox{XYZ} -> XYZ
        pattern = re.compile(re.escape(cmd) + r"\s*\{([^{}]*)\}")
        source = pattern.sub(lambda m: m.group(1), source)
    return source


def _apply_replacements(source: str) -> str:
    for old, new in _REPLACE_CMDS.items():
        source = source.replace(old, new)
    return source


def _drop_cmds(source: str) -> str:
    for cmd in _DROP_CMDS:
        source = source.replace(cmd, " ")
    # 环境之外的行分隔符 \\ 对 mathtext 无意义，替换为空格；
    # 环境（matrix/cases 等）内部的 \\ 必须保留。做法：逐段扫描，
    # 对 \begin{...} ... \end{...} 之外的 \\ 做替换。
    out: list[str] = []
    pos = 0
    env_depth = 0
    begin = re.compile(r"\\begin\{[^}]*\}")
    end = re.compile(r"\\end\{[^}]*\}")
    while pos < len(source):
        mb = begin.search(source, pos)
        me = end.search(source, pos)
        nxt = mb if (mb and (not me or mb.start() < me.start())) else me
        if nxt is None:
            tail = source[pos:]
            if env_depth == 0:
                tail = tail.replace(r"\\", " ")
            out.append(tail)
            break
        tail = source[pos:nxt.start()]
        if env_depth == 0:
            tail = tail.replace(r"\\", " ")
        out.append(tail)
        out.append(nxt.group(0))
        if nxt is mb:
            env_depth += 1
        else:
            env_depth = max(0, env_depth - 1)
        pos = nxt.end()
    return "".join(out)


def _fix_quad_spaces(source: str) -> str:
    # \quad / \qquad 在 mathtext 支持；\enspace / \hspace{...} 不支持
    source = source.replace(r"\enspace", " ")
    source = re.sub(r"\\(?:hspace|vspace)\*?\s*\{[^{}]*\}", " ", source)
    source = re.sub(r"\\(?:hspace|vspace)\*?\s*\[[^\]]*\]\{[^{}]*\}", " ", source)
    return source


def _ensure_math_wrap(tex: str) -> str:
    tex = tex.strip()
    if tex.startswith("$$") and tex.endswith("$$"):
        tex = tex[2:-2]
    elif tex.startswith("$") and tex.endswith("$") and not tex.startswith(r"\$"):
        tex = tex[1:-1]
    elif tex.startswith(r"\[") and tex.endswith(r"\]"):
        tex = tex[2:-2]
    elif tex.startswith(r"\(") and tex.endswith(r"\)"):
        tex = tex[2:-2]
    return f"${tex}$"


def preprocess(source: str) -> str:
    """对单段公式源码做确定性改写，返回可送 mathtext 的 ``$…$`` 字符串。"""
    tex = _strip_comments(source)
    tex = _drop_tag(tex)
    # \label/\ref/\eqref 由编号层（numbering.resolve）处理；
    # 若仍残留（单独渲染场景），避免把未知命令送进 mathtext：
    # \ref 退化为 "?"，\eqref 退化为 "(?)"
    tex = re.sub(r"\\eqref\s*\{[^{}]*\}", "(?)", tex)
    tex = re.sub(r"\\(?:ref|pageref)\s*\{[^{}]*\}", "?", tex)
    tex = re.sub(r"\\label\s*\{[^{}]*\}", "", tex)
    tex = _convert_envs(tex)
    tex = _unwrap_cmds(tex)
    tex = _apply_replacements(tex)
    tex = _fix_quad_spaces(tex)
    tex = _drop_cmds(tex)
    tex = re.sub(r"\\newcommand\*?(?:\\[a-zA-Z]+)?(?:\[[0-9]+\])?\s*\{[^{}]*\}",
                 " ", tex)
    tex = re.sub(r"\\renewcommand\*?(?:\\[a-zA-Z]+)?(?:\[[0-9]+\])?\s*\{[^{}]*\}",
                 " ", tex)
    return _ensure_math_wrap(tex)
