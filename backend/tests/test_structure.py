"""结构解析、错误定位与拼写建议测试。

重点守死题目判据：
- 缺少右花括号的错误位置落在真正缺括号的地方（源码末尾）附近；
- 错误码、行列号、拼写建议均有明确契约。
"""
from __future__ import annotations

import pytest

from app.parser.spelling import _damerau_levenshtein, suggest
from app.parser.structure import check_structure


def codes(source):
    return [e.code for e in check_structure(source).errors]


def test_balanced_source_is_ok():
    assert check_structure(r"\frac{a}{b} + \sqrt{x}").ok
    assert check_structure(r"\left(\frac{1}{2}\right)").ok
    assert check_structure(r"\begin{matrix} a & b \\ c & d \end{matrix}").ok


def test_missing_rbrace_points_at_eof_location():
    src = r"x = \frac{a}{b"  # 第二组缺 }
    result = check_structure(src)
    assert not result.ok
    err = next(e for e in result.errors if e.code == "missing_rbrace")
    # 真正缺括号的位置：源码末尾
    assert err.offset == len(src)
    assert err.line == 1
    assert err.column == len(src) + 1
    # 消息里必须提到左括号所在行（帮助定位）
    assert "1" in err.message


def test_missing_rbrace_multiline_reports_correct_line():
    lines = ["y = \\sqrt{", "  x + ", "  \\frac{1}{2}", "]"]
    src = "\n".join(lines)  # sqrt 参数始终没闭合
    result = check_structure(src)
    err = next(e for e in result.errors if e.code == "missing_rbrace")
    assert err.offset == len(src)
    assert err.line == src.count("\n") + 1


def test_extra_rbrace_is_locally_located():
    src = r"a + b}"
    result = check_structure(src)
    err = next(e for e in result.errors if e.code == "unmatched_delimiter")
    assert err.offset == src.index("}")
    assert err.line == 1 and err.column == src.index("}") + 1


def test_missing_argument_for_frac():
    result = check_structure(r"\frac{a}")
    msgs = [e for e in result.errors
            if e.code == "missing_argument" or e.code == "missing_rbrace"]
    assert msgs
    # \frac 缺第二参数时必须能定位到命令附近而非崩溃
    frac_err = next(e for e in result.errors
                    if e.code == "missing_argument")
    assert frac_err.message.startswith(r"命令 \frac")


def test_frac_missing_both_args_at_eof():
    result = check_structure(r"value = \frac")
    assert any(e.code == "missing_argument" for e in result.errors)


def test_bracket_and_paren_pairs():
    assert check_structure("[a] + (b) + {c}").ok


def test_unclosed_bracket():
    result = check_structure("[a + b")
    assert any(e.code == "missing_close" for e in result.errors)


def test_left_right_pair_ok():
    assert check_structure(r"\left[ \frac{a}{b} \right]").ok
    assert check_structure(r"\left. \frac{dy}{dx} \right|_0").ok


def test_missing_right():
    result = check_structure(r"\left( a+b")
    assert any(e.code == "missing_right" for e in result.errors)


def test_unmatched_right_alone():
    result = check_structure(r"a+b\right)")
    assert any(e.code == "unmatched_right" for e in result.errors)


def test_left_right_delimiter_mismatch():
    result = check_structure(r"\left( a \right]")
    assert any(e.code == "left_right_mismatch" for e in result.errors)


def test_environment_pair_ok_and_nested():
    src = (r"\begin{aligned} x &= 1 \\ y &= "
           r"\begin{cases} a \\ b \end{cases} \end{aligned}")
    assert check_structure(src).ok


def test_missing_end_reports_env_name():
    result = check_structure(r"\begin{matrix} a & b \\ c & d")
    err = next(e for e in result.errors if e.code == "missing_end")
    assert "matrix" in err.message
    assert err.offset == len(r"\begin{matrix} a & b \\ c & d")


def test_env_name_mismatch():
    result = check_structure(r"\begin{matrix} a \end{pmatrix}")
    assert any(e.code == "env_name_mismatch" for e in result.errors)


def test_end_without_begin():
    result = check_structure(r"a \end{aligned}")
    assert any(e.code == "unmatched_end" for e in result.errors)


def test_comments_do_not_break_structure():
    src = "\\frac{a}{b} % missing? no it's fine\n"
    assert check_structure(src).ok


def test_unknown_command_with_spelling_suggestion():
    result = check_structure(r"\farc{1}{2}")  # frac 的拼写错误
    err = next(e for e in result.errors if e.code == "unknown_command")
    assert err.suggestion == "frac"
    assert err.offset == 0
    assert "frac" in err.message


def test_unknown_command_theta_typo():
    result = check_structure(r"\theeta")
    err = next(e for e in result.errors if e.code == "unknown_command")
    assert err.suggestion == "theta"


def test_genuinely_custom_command_is_not_flagged():
    # 与任何已知命令都不相近的名字视为自定义宏，容错放行
    result = check_structure(r"\mycustommacro{x}")
    assert all(e.code != "unknown_command" for e in result.errors)


def test_control_symbols_not_spell_checked():
    assert check_structure(r"a\,b \; c \!").ok


@pytest.mark.parametrize("a,b,dist", [
    ("frac", "frac", 0),
    ("farc", "frac", 1),   # 换位
    ("theeta", "theta", 1),
    ("xyz", "frac", 4),
])
def test_edit_distance(a, b, dist):
    assert _damerau_levenshtein(a, b) == dist


def test_suggest_threshold():
    assert suggest(r"\farc") == "frac"
    assert suggest("zzzzzzzz") is None


def test_error_serialization_contract():
    result = check_structure(r"\farc{a}{b}")
    payload = result.to_dict()
    err = payload["errors"][0]
    assert {"code", "message", "offset", "line", "column",
            "end_offset", "suggestion"} <= set(err)
    assert payload["tokens"], "tokens 必须返回，供前端高亮"
