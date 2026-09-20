"""真正在后端把 LaTeX 排版为 SVG 的渲染器。

使用 matplotlib 的 mathtext（Agg + SVG 后端，完全在服务端进程内完成，
不依赖外部 latex 二进制）。每条公式得到独立 SVG，以 data-URI 内联进
HTML 片段返回给前端，前端只负责呈现。

容错策略（tolerant=True）见 :func:`render_tolerant`：
1. 先整段尝试；整段成功就返回单图；
2. 整段失败则尝试“保守修复”（仅补缺失右花括号）后整段渲染；
3. 再失败则按 ``parser.tolerant`` 的切分逐段独立渲染，
   失败片段替换为红色占位，保证一处局部错误不吃掉其它可渲染内容。
"""
from __future__ import annotations

import base64
import html as html_mod
import io
import re
import threading

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.font_manager import FontProperties  # noqa: E402
from matplotlib.mathtext import MathTextParser  # noqa: E402

from ..parser.tolerant import repair_unbalanced, segment_source
from .matrices import (_DELIMITERS, delimiter_html, find_top_environments,
                       split_cells)
from .preprocess import preprocess

_parser = MathTextParser("agg")
_lock = threading.Lock()
_cache: dict[tuple[str, int], tuple[str, float, float]] = {}
_CACHE_MAX = 512


class RenderError(Exception):
    """排版失败；message 为可展示的错误描述。"""


# ------------------------------------------------------------------ primitives

def _font(fontsize: int) -> FontProperties:
    # 新版 matplotlib（3.11+）不再接受 parse(fontsize=...)，字号必须随字体传入
    try:
        return FontProperties(family="DejaVu Sans", size=fontsize)
    except TypeError:  # 极旧版本 FontProperties 无 size 关键字
        fp = FontProperties(family="DejaVu Sans")
        fp.set_size(fontsize)
        return fp


def _parse_box(tex_math: str, fontsize: int, dpi: int = 100):
    """兼容 matplotlib 新旧两版 mathtext API，返回 (width, height) 像素。"""
    with _lock:
        result = _parser.parse(tex_math, dpi=dpi, prop=_font(fontsize))
    # 新版（3.11+）：RasterParse(ox, oy, width, height, depth, image)
    if hasattr(result, "width"):
        return float(result.width), float(result.height) + float(
            getattr(result, "depth", 0.0))
    # 旧版：(width, height, depth, ...) 元组
    width, height = result[0], result[1]
    depth = result[2] if len(result) > 2 else 0
    return float(width), float(height) + float(depth or 0)


def _size_in_pixels(tex_math: str, fontsize: int = 18) -> tuple[float, float]:
    """用 mathtext 预估排版尺寸（像素），失败抛 ValueError。"""
    return _parse_box(tex_math, fontsize)


def _raw_svg(tex_math: str, fontsize: int, dpi: int = 100) -> str:
    """把已经包在 ``$…$`` 中的 mathtext 渲染为 SVG 字符串。"""
    width_px, height_px = _size_in_pixels(tex_math, fontsize)
    fig = Figure(figsize=(width_px / dpi + 0.08, height_px / dpi + 0.08),
                 dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.text(0.0 + 0.04 / fig.get_figwidth(), 0.5, tex_math,
            fontproperties=_font(fontsize),
            ha="left", va="center")
    buf = io.BytesIO()
    fig.savefig(buf, format="svg", transparent=True, bbox_inches="tight",
                pad_inches=0.02)
    plt.close(fig)
    return buf.getvalue().decode("utf-8")


_WIDTH_RE = None  # 宽度直接取自 mathtext 的 parse 结果


def render_tex(tex: str, fontsize: int = 18) -> dict:
    """渲染单段（已经是 mathtext 可接受文本，可不带 $）为 SVG。

    返回 {"svg", "width_px", "height_px", "html"}。失败抛 :class:`RenderError`。
    """
    math_tex = tex if tex.strip().startswith("$") else f"${tex.strip()}$"
    cache_key = (math_tex, fontsize)
    cached = _cache.get(cache_key)
    if cached is not None:
        svg, width_px, height_px = cached
    else:
        try:
            svg = _raw_svg(math_tex, fontsize)
            width_px, height_px = _size_in_pixels(math_tex, fontsize)
        except Exception as exc:  # mathtext raises ValueError variants
            raise RenderError(str(exc).splitlines()[0]) from exc
        if len(_cache) >= _CACHE_MAX:
            _cache.clear()
        _cache[cache_key] = (svg, width_px, height_px)

    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    html = (f'<img class="tex-img" alt="" loading="lazy" '
            f'style="height:{height_px * 0.72:.1f}px;width:auto;'
            f'vertical-align:middle;margin:0 1px" '
            f'src="data:image/svg+xml;base64,{b64}"/>')
    return {
        "svg": svg,
        "width_px": width_px,
        "height_px": height_px,
        "html": html,
    }


# ------------------------------------------------------------- composite API

def _error_placeholder(text: str, message: str) -> str:
    safe = (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))
    msg = (message or "无法渲染的片段").replace('"', "'").splitlines()[0][:160]
    return (f'<span class="tex-error" data-source="{safe}" '
            f'title="{msg}">{safe}</span>')


def _render_cell(tex: str, fontsize: int) -> str:
    """渲染矩阵单元格：空单元格占位；内含嵌套环境时递归走环境渲染。"""
    if tex.strip() == "":
        return '<span class="env-cell env-cell-empty"></span>'
    if find_top_environments(tex):
        inner = render_piece(tex, fontsize)
    else:
        inner = render_tex(preprocess(tex), fontsize)["html"]
    return f'<span class="env-cell">{inner}</span>'


def _render_environment(env: str, body: str, fontsize: int) -> str:
    rows = split_cells(body, env)
    left_d, right_d = _DELIMITERS.get(env, ("", ""))
    grid = (
        f'<span class="env-matrix env-{env}">'
        f'{delimiter_html(left_d, "left")}'
        f'<span class="env-grid" style="grid-template-columns:repeat('
        f'{max(1, max((len(r) for r in rows), default=1))}, max-content)">'
    )
    for r in rows:
        for cell in r:
            grid += _render_cell(cell, fontsize)
    grid += "</span>" + delimiter_html(right_d, "right") + "</span>"
    return grid


def render_piece(source: str, fontsize: int = 18) -> str:
    """渲染一段可能含矩阵/对齐/cases 环境的数学源码为 HTML。

    环境块结构化为 HTML 网格，环境外文本走 mathtext；中日韩等排版正文字符
    不进 mathtext（会出缺字方框），而是作为普通 HTML 文本内联，保证混排可读。
    """
    envs = find_top_environments(source)
    if not envs:
        return _render_math_with_prose(source, fontsize)

    parts: list[str] = []
    cursor = 0
    for block in envs:
        if block["start"] > cursor:
            parts.append(_render_math_with_prose(
                source[cursor:block["start"]], fontsize))
        body = source[block["body_start"]:block["body_end"]]
        parts.append(_render_environment(block["env"], body, fontsize))
        cursor = block["end"]
    if cursor < len(source):
        parts.append(_render_math_with_prose(source[cursor:], fontsize))
    return "".join(parts)


# 排版正文字符（CJK、中文标点等），mathtext 没有这些字形
_PROSE_RE = re.compile(
    r"[　-〿㐀-䶿一-鿿豈-﫿＀-￯]"
)


def _split_prose(tex: str) -> list[tuple[str, bool]]:
    """把源码切成有序片段：[(text, is_prose)]，并消化已有的 \text/\mathrm 包裹。"""
    runs: list[tuple[str, bool]] = []
    i = 0
    n = len(tex)
    while i < n:
        ch = tex[i]
        # \text{...} / \mathrm{...} 的组体本身就是正文（mathtext 下中文仍缺字，
        # 故直接抽出作为 prose，不再交给 mathtext）
        m = re.match(r"\\(?:text|mathrm|operatorname)\s*\{", tex[i:])
        if m:
            body_start = i + m.end()
            depth = 1
            j = body_start
            while j < n and depth > 0:
                if tex[j] == "{":
                    depth += 1
                elif tex[j] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            runs.append((tex[body_start:j], True))
            i = j + 1
            continue
        if _PROSE_RE.search(ch):
            if runs and runs[-1][1] is True:
                runs[-1] = (runs[-1][0] + ch, True)
            else:
                runs.append((ch, True))
            i += 1
            continue
        if runs and runs[-1][1] is False:
            runs[-1] = (runs[-1][0] + ch, False)
        else:
            runs.append((ch, False))
        i += 1
    return runs


def _render_math_with_prose(source: str, fontsize: int) -> str:
    """混排：数学运行 SVG，CJK/正文运行普通 HTML；任一数学运行失败即抛错。"""
    runs = _split_prose(source)
    parts: list[str] = []
    for text, is_prose in runs:
        if is_prose:
            parts.append(
                f'<span class="tex-prose">{html_mod.escape(text)}</span>')
            continue
        if text.strip() == "":
            parts.append(html_mod.escape(text))
            continue
        parts.append(render_tex(preprocess(text), fontsize)["html"])
    return "".join(parts)


def _has_environment(source: str) -> bool:
    return bool(find_top_environments(source))


def render_strict(source: str, fontsize: int = 18) -> dict:
    """非容错渲染：成功返回 HTML（可能是单图或“图+矩阵网格”组合）。"""
    html_out = render_piece(source, fontsize)
    svg = None
    width_px = height_px = None
    if not _has_environment(source):
        # 纯单图路径额外附带 svg 与尺寸，便于测试/复用
        out = render_tex(preprocess(source), fontsize)
        svg, width_px, height_px = out["svg"], out["width_px"], out["height_px"]
    return {
        "ok": True,
        "html": f'<span class="tex-formula">{html_out}</span>',
        "svg": svg,
        "width_px": width_px,
        "height_px": height_px,
        "segments": [{
            "text": source, "kind": "math", "ok": True,
            "html": html_out, "repaired": None,
        }],
    }


def render_tolerant(source: str, fontsize: int = 18) -> dict:
    """容错渲染：尽最大努力呈现，出错片段以醒目占位标记代替。"""
    # 1) 整段直出
    try:
        result = render_strict(source, fontsize)
        result["repaired"] = False
        return result
    except RenderError as first_err:
        first_message = str(first_err)

    # 2) 保守修复（补右花括号）后整段渲染
    repaired, added = repair_unbalanced(source)
    if added:
        try:
            html_out = render_piece(repaired, fontsize)
            marker = _error_placeholder(" " + "}" * added,
                                        f"已自动补入 {added} 个右花括号")
            return {
                "ok": True,
                "repaired": True,
                "html": (f'<span class="tex-formula">{html_out}'
                         f"{marker}</span>"),
                "svg": None,
                "width_px": None,
                "height_px": None,
                "segments": [{
                    "text": source, "kind": "math", "ok": True,
                    "html": html_out,
                    "repaired": repaired,
                }],
            }
        except RenderError:
            pass

    # 3) 切分逐段渲染
    segments = segment_source(source)
    parts: list[str] = []
    seg_payload: list[dict] = []
    any_ok = False
    for seg in segments:
        if seg.kind == "space":
            # 保留原始空白（换行给一个最小间距）
            visible = seg.text.replace("\n", " ​")
            parts.append(
                f'<span class="tex-space">'
                f'{visible.replace(" ", "&nbsp;")}</span>')
            seg_payload.append({"text": seg.text, "kind": "space",
                                "ok": True, "html": "",
                                "repaired": None})
            continue
        seg_repaired, seg_added = repair_unbalanced(seg.text)
        try:
            piece_html = render_piece(seg_repaired, fontsize)
            parts.append(piece_html)
            any_ok = True
            seg_payload.append({
                "text": seg.text, "kind": "math", "ok": True,
                "html": piece_html,
                "repaired": seg_repaired if seg_added else None,
                "start": seg.start, "end": seg.end,
            })
        except RenderError as exc:
            parts.append(_error_placeholder(seg.text, str(exc)))
            seg_payload.append({
                "text": seg.text, "kind": "math", "ok": False,
                "html": None, "error": str(exc),
                "start": seg.start, "end": seg.end,
            })

    return {
        "ok": any_ok,
        "repaired": False,
        "html": (f'<span class="tex-formula tex-tolerant">'
                 f'{"".join(parts)}</span>'),
        "svg": None,
        "fatal": first_message if not any_ok else None,
        "segments": seg_payload,
    }
