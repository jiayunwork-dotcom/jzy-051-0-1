"""未知命令的拼写建议。

当结构解析遇到未知命令时，用 Damerau–Levenshtein 编辑距离在已知命令表中找
最接近的候选，距离不超过 ``MAX_DISTANCE`` 才给出建议，否则认为它可能是用户
自定义宏而不报错（由调用方按建议存在与否决定是否产出语法错误）。
"""
from __future__ import annotations

MAX_DISTANCE = 2

# 常见数学命令白名单（也是前端补全/高亮可参考的词表）
KNOWN_COMMANDS: tuple[str, ...] = (
    # 希腊字母
    "alpha", "beta", "gamma", "delta", "epsilon", "varepsilon", "zeta", "eta",
    "theta", "vartheta", "iota", "kappa", "lambda", "mu", "nu", "xi",
    "omicron", "pi", "varpi", "rho", "varrho", "sigma", "varsigma", "tau",
    "upsilon", "phi", "varphi", "chi", "psi", "omega",
    "Gamma", "Delta", "Theta", "Lambda", "Xi", "Pi", "Sigma", "Upsilon",
    "Phi", "Psi", "Omega",
    # 运算符 / 函数
    "frac", "dfrac", "tfrac", "sqrt", "sum", "prod", "int", "oint", "iint",
    "iiint", "lim", "limsup", "liminf", "log", "ln", "exp", "sin", "cos",
    "tan", "cot", "sec", "csc", "arcsin", "arccos", "arctan", "sinh",
    "cosh", "tanh", "min", "max", "sup", "inf", "det", "dim", "gcd",
    "cdot", "cdots", "ldots", "vdots", "ddots", "times", "div", "pm", "mp",
    "ast", "star", "circ", "bullet", "oplus", "ominus", "otimes", "oslash",
    "odot", "dagger", "ddagger", "setminus", "bmod", "pmod",
    # 关系
    "leq", "le", "geq", "ge", "neq", "ne", "approx", "equiv", "sim", "simeq",
    "cong", "propto", "ll", "gg", "doteq", "models", "perp", "parallel",
    "mid", "subset", "supset", "subseteq", "supseteq", "subsetneq",
    "supsetneq", "sqsubset", "sqsubseteq", "prec", "succ", "preceq",
    "succeq", "in", "ni", "notin",
    # 箭头
    "leftarrow", "rightarrow", "leftrightarrow", "Leftarrow", "Rightarrow",
    "Leftrightarrow", "longleftarrow", "longrightarrow", "mapsto",
    "longmapsto", "uparrow", "downarrow", "updownarrow", "Uparrow",
    "Downarrow", "iff", "implies", "to",
    # 结构 / 环境
    "begin", "end", "left", "right", "middle", "mathnormal", "mathrm",
    "mathbf", "mathit", "mathsf", "mathtt", "mathcal", "mathbb", "mathfrak",
    "mathscr", "operatorname", "overline", "underline", "overbrace",
    "underbrace", "hat", "widehat", "bar", "vec", "tilde", "widetilde",
    "dot", "ddot", "breve", "check", "acute", "grave", "overline",
    # 矩阵 / 对齐
    "matrix", "pmatrix", "bmatrix", "Bmatrix", "vmatrix", "Vmatrix",
    "cases", "array", "aligned", "gathered",
    # 间距 / 样式
    "displaystyle", "textstyle", "scriptstyle", "scriptscriptstyle",
    "quad", "qquad", "thinspace", "medspace", "thickspace", "colon",
    "label", "ref", "eqref", "tag", "nonumber", "text", "boxed", "frac",
    "root", "substack", "binom", "tbinom", "dbinom", "cancel",
    # 定界
    "langle", "rangle", "lfloor", "rfloor", "lceil", "rceil", "lbrace",
    "rbrace", "lvert", "rvert", "lVert", "rVert",
    # 杂项
    "infty", "partial", "nabla", "forall", "exists", "nexists", "varnothing",
    "emptyset", "angle", "triangle", "square", "clubsuit", "diamondsuit",
    "heartsuit", "spadesuit", "aleph", "hbar", "ell", "wp", "Re", "Im",
    "prime", "backslash", "cdots", "dots", "dotsc", "dotsb", "dotsm",
    "therefore", "because", "degree",
    # \big 家族
    "big", "Big", "bigg", "Bigg", "bigl", "bigr", "Bigl", "Bigr",
    "limits", "nolimits", "displaystyle",
)

# 去重（保留顺序仅为稳定输出）
KNOWN_UNIQUE: tuple[str, ...] = tuple(dict.fromkeys(KNOWN_COMMANDS))


def _damerau_levenshtein(a: str, b: str) -> int:
    """相邻换位也算 1 的编辑距离。"""
    la, lb = len(a), len(b)
    prev_prev: list[int] = []
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        cur = [i] + [0] * lb
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(
                prev[j] + 1,        # 删除
                cur[j - 1] + 1,     # 插入
                prev[j - 1] + cost, # 替换
            )
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                cur[j] = min(cur[j], prev_prev[j - 2] + cost)
        prev_prev = prev
        prev = cur
    return prev[lb]


def suggest(name: str, max_distance: int = MAX_DISTANCE) -> str | None:
    """返回最近似的已知命令名（不含反斜杠），没有足够接近的候选时返回 None。"""
    name = name.lstrip("\\")
    best: str | None = None
    best_d = max_distance + 1
    for candidate in KNOWN_UNIQUE:
        # 明显不相关长度的候选提前跳过
        if abs(len(candidate) - len(name)) > max_distance:
            continue
        d = _damerau_levenshtein(name, candidate)
        if d < best_d:
            best_d = d
            best = candidate
    return best if best_d <= max_distance else None
