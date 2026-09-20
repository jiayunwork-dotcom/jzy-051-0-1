# LaTeX 数学公式编辑器

一个在浏览器里使用的 LaTeX 数学公式创作工具：左侧敲源码、右侧实时渲染，
可管理一份文稿中的多个公式并在公式间交叉引用。**解析、编号、校验、渲染全部
在后端完成**，前端只负责编辑与呈现。

- 前端：React 18 + Vite（Node.js 20 构建）
- 后端：Python 3.12 + FastAPI
- 数据库：PostgreSQL 16（乐观锁版本号，防并发覆盖）
- 渲染：服务端 matplotlib mathtext 生成 SVG；矩阵/cases/对齐环境由后端
  结构化为 HTML 网格（mathtext 本身不支持 `\begin{matrix}`）
- 编排：Docker Compose（db / backend / frontend 三容器）

## 一键启动

```bash
docker compose up --build
```

- 浏览器打开 http://localhost:8080
- 后端 API 文档：http://localhost:8000/docs
- 运行自动化测试（在已启动的后端容器内，含数据库测试）：
  ```bash
  docker compose exec backend pytest -q
  ```
- 停止：`Ctrl+C` 后 `docker compose down -v`（`-v` 同时清库）

首次打开会自动创建一个带两条示例公式（含 `\label` / `\eqref` 交叉引用）的
工作区。

## 功能对照

| 需求 | 实现位置 |
| --- | --- |
| 行号 + 语法高亮（命令/花括号/符号/注释分色） | `frontend/src/components/CodeEditor.jsx` |
| 括号匹配高亮、花括号自动补全/选区包裹 | 同上（`findMatch` / `handleKeyDown`） |
| 可拖动左右分栏 | `frontend/src/components/SplitPane.jsx` |
| 停止输入 150ms 后渲染 | `frontend/src/App.jsx`（`RENDER_DEBOUNCE_MS`） |
| 符号面板（希腊/运算/关系/箭头/结构）+ 矩阵模板 + 最近使用 | `components/SymbolPanel.jsx` + `data/symbols.js` |
| 公式模板库（定积分、矩阵乘法、正态分布、方程组等） | `components/TemplatePanel.jsx` |
| 多公式、自动顺序编号、可选标签、拖拽重排 | `components/FormulaList.jsx` + 后端 `app/xrefs/numbering.py` |
| `\ref`/`\eqref` 交叉引用显示真实编号 | 后端 `numbering.resolve` |
| 重排后编号与所有引用数字自动同步 | 同一函数，编号只取决于位置；见 `tests/test_numbering.py` |
| 引用不存在标签 / 重复标签 / 成环引用三类异常 | `numbering.py`（`undefined_label` / `duplicate_label` / `ref_cycle`） |
| 词法分析 | `app/parser/lexer.py` |
| 花括号、`\left\right`、`\begin\end` 配对与命令闭合 | `app/parser/structure.py` |
| 错误定位到行/列/偏移；缺右花括号定位在真正缺失处 | 同上，`ParseError` 契约 |
| 未知命令拼写建议 | `app/parser/spelling.py`（Damerau–Levenshtein ≤ 2） |
| 容错切分 + 错误片段红色占位 | `app/parser/tolerant.py` + `render/renderer.py` |
| 工作区/公式/标签/顺序/自定义模板持久化 | `app/db/repository.py`（JSONB 整文档存储） |
| 并发保存互不覆盖 | `version` 乐观锁，冲突返回 HTTP 409 |

## 正确性契约（测试守死）

后端测试（72 个，随容器构建可用 `docker compose exec backend pytest` 运行）：

```bash
cd backend
python -m pytest -q
```

关键判据对应测试：

- `tests/test_numbering.py`
  - `test_reorder_renumbers_everything_and_all_refs_follow`：交换顺序后，
    每个公式新编号与所有 `\ref` 数字必须与新顺序一致；
  - `test_undefined_label_is_detected_and_never_silently_numbered`；
  - `test_duplicate_labels_are_detected`；
  - `test_mutual_reference_cycle_is_detected` / `test_self_reference_is_a_cycle`。
- `tests/test_structure.py`
  - `test_missing_rbrace_points_at_eof_location`：缺右花括号的
    `offset/line/column` 落在源码末尾的真正缺失处；
  - `test_unknown_command_with_spelling_suggestion`：`\farc` → 建议 `\frac`；
  - 环境、`\left\right`、命令参数闭合等。
- `tests/test_tolerant.py`：片段拼回等于原文、顶级好片段不被错误片段吃掉。
- `tests/test_render.py` / `test_matrices.py` / `test_services.py`：
  容错渲染局部错误不白屏，矩阵/cases 结构化输出。
- `tests/test_repository.py`：乐观锁拒绝陈旧写入（需要 PostgreSQL；
  本地无库时自动 skip，容器中执行）。

## HTTP 接口

- `POST /api/analyze`
  请求：`{"formulas": [{"id", "source", "label"}], "base", "tolerant", "fontsize"}`
  返回：每个公式的编号、`rendered_source`（`\ref` 已替换为数字）、
  结构错误、交叉引用错误、后端渲染的 HTML（内联 SVG / 矩阵网格），以及
  全局 `label_to_number` 与 `xref_errors`。
- `POST /api/parse`：单段源码的 token 流与结构错误（高亮/提示）。
- `GET/POST /api/workspaces`、`GET/PUT/DELETE /api/workspaces/{id}`：
  PUT 必须带 `expected_version`，版本不匹配返回 `409`。

## 目录结构

```
backend/
  app/
    parser/lexer.py        词法
    parser/structure.py    配对/闭合/错误定位
    parser/spelling.py     拼写建议
    parser/tolerant.py     容错切分
    xrefs/numbering.py     编号、引用、三类异常（可独立验证的核心）
    render/preprocess.py   LaTeX → mathtext 子集
    render/matrices.py     矩阵/cases/对齐环境结构化
    render/renderer.py     服务端 SVG 渲染与容错编排
    db/repository.py       PostgreSQL + 乐观锁
    api.py / services.py / schemas.py / main.py
  tests/                   72 个自动化测试
frontend/
  src/
    components/CodeEditor.jsx / Preview.jsx / SymbolPanel.jsx
               TemplatePanel.jsx / FormulaList.jsx / SplitPane.jsx
    data/symbols.js        符号与模板库数据
    api.js                 所有解析/渲染都走后端
docker-compose.yml
```

## 本地开发（不用 Docker）

- 后端：`cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload`
  （需可连接的 PostgreSQL 16，用 `DATABASE_URL` 指定）
- 前端：`cd frontend && npm install && npm run dev`
  （Vite 已把 `/api` 代理到 `http://localhost:8000`）
