"""容错切分器测试：契约级断言，保证局部错误不吃掉可渲染内容。"""
from __future__ import annotations

from app.parser.tolerant import repair_unbalanced, segment_source


def test_segments_cover_whole_source():
    src = r"a + b = \frac{c}{d}"
    segs = segment_source(src)
    # 片段拼回来必须与原文一致
    assert "".join(s.text for s in segs) == src
    # 偏移区间与文本一致
    for s in segs:
        assert src[s.start:s.end] == s.text


def test_split_points_at_top_level_only():
    # 花括号内部的 + 不应导致切分
    src = r"\frac{a+b}{c-d}"
    segs = segment_source(src)
    # 整个 \frac{..}{..} 是一个命令原子（成组后立即断片），
    # 其文本必须完整保留 a+b
    frac_seg = next(s for s in segs if s.kind == "math")
    assert "a+b" in frac_seg.text


def test_unclosed_brace_kept_in_last_segment_without_swallowing():
    # 未闭合花括号后面若还有顶级内容，顶级内容必须仍是独立可渲染片段
    src = "x + {broken + y = z"
    segs = segment_source(src)
    texts = [s.text for s in segs if s.kind == "math"]
    # "x" 必须在错误片段之前独立存在
    assert texts[0] == "x"
    # 等号作为独立 split 片段，"z" 不会被卷走
    assert "z" in texts
    assert "".join(s.text for s in segs) == src


def test_whitespace_preserved_as_segments():
    src = "a   b"
    segs = segment_source(src)
    assert any(s.kind == "space" and "   " in s.text for s in segs)


def test_repair_adds_only_trailing_braces():
    repaired, n = repair_unbalanced(r"\frac{a}{b")
    assert n == 1
    assert repaired.endswith("}")
    repaired2, n2 = repair_unbalanced("a{b{c}")
    assert n2 == 1
    ok, n0 = repair_unbalanced("a{b}c")
    assert n0 == 0 and ok == "a{b}c"


def test_segment_offsets_are_accurate():
    src = "alpha + beta"
    for s in segment_source(src):
        assert src[s.start:s.end] == s.text
