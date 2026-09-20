"""LaTeX 数学公式编辑器后端。

模块划分：
- app.parser.lexer      词法切分
- app.parser.structure  括号 / \\left\\right / 环境配对与命令闭合检查
- app.parser.spelling   未知命令的拼写建议
- app.parser.tolerant   容错切分
- app.xrefs.numbering   标签解析、顺序编号、交叉引用与三类异常检测
- app.render            LaTeX -> SVG 的后端渲染
- app.db                PostgreSQL 持久化（乐观锁版本号）
"""
