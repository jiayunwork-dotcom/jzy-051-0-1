# LaTeX 数学公式编辑器

一个浏览器内使用的 LaTeX 数学公式创作工具：左侧敲源码、右侧实时排版，支持
一份工作区里管理多个公式、拖拽排序与 `\ref{标签}` 交叉引用。**所有决定正确性
的工作——词法/结构解析、错误定位与拼写建议、编号重排与交叉引用校验、容错
渲染——都在后端（Python 3.12 + FastAPI）完成并可被自动化测试逐条覆盖**；
前端（React + Vite）只负责编辑与呈现。

## 技术栈与运行环境（固定版本）

| 组件 | 版本 |
| --- | --- |
| 前端构建 | Node.js 20（React 18 + Vite 5 + TypeScript） |
| 后端 | Python 3.12 + FastAPI + SQLAlchemy 2（async） |
| 数据库 | PostgreSQL 16 |
| 编排 | Docker Compose |

## 一键启动

```bash
docker compose up --build
# 浏览器打开
#   http://localhost:8080        ← 前端（nginx 反代 /api 到后端）
#   http://localhost:8000/docs   ← FastAPI 接口文档
```

本地开发（不用容器）：

```bash
# 后端
cd backend
python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+asyncpg://latex:latex@localhost:5432/latex_editor
uvicorn app.main:app --reload

# 前端（自动把 /api 代理到 localhost:8000）
cd frontend
npm install
npm run dev          # http://localhost:5173
```

## 自动化测试

```bash
./run-tests.sh            # 本地（默认内存 SQLite，内核测试与数据库无关）
./run-tests.sh docker     # 在 compose 里跑（tests profile）
# 或手动
cd backend && python -m pytest app/tests -v
```

测试覆盖了需求中必须“守死”的四类判据：

1. **编号重排**：重排后每个公式的新编号、所有 `\ref` 显示的数字都与新顺序一致
   （`test_reorder_updates_all_reference_numbers` 等）。
2. **交叉引用三类异常**：引用不存在标签、重复标签、相互引用成环（含自环）都被
   检测并明确报错，绝不静默给出错误数字。
3. **错误位置定位**：缺少右花括号时报错位置落在真正的开括号上（带行/列），
   未知命令给出基于 Damerau–Levenshtein 的拼写建议。
4. **容错渲染**：局部错误只染红出错片段（`<merror>` 占位），周围可正确渲染的
   表达式一个都不会被吃掉；并有显式的好/坏片段（segments）契约。

## 功能一览

- 左侧带行号的源码编辑区：命令/花括号/数学符号/注释四类语法高亮、括号匹配高亮、
  花括号（`{}`、`()`、`[]`）自动补全与选区包裹、Tab 缩进。
- 中间可拖动分隔条调整左右两栏比例。
- 停止输入约 **150ms** 后触发一次后端 `/api/preview`（避免逐字符重排）。
- 右侧实时 MathML 预览 + 公式编号；下方列出解析错误（行:列、信息、拼写建议）
  与交叉引用问题（未定义/重复/成环）。
- 底部可折叠符号面板：希腊字母、运算符、关系符号、箭头、矩阵模板、常用结构，
  点击即在光标处插入，并单独维护一栏“最近使用”（localStorage）。
- 公式模板库：定积分、矩阵乘法、正态分布、方程组等，可一键插入骨架再改参数；
  支持把当前片段“存为模板”（随工作区持久化）。
- 工作区左侧公式列表：自动顺序编号、可选标签、拖拽排序、增删；排序后编号与
  全部引用数字由后端重新解析。
- 工作区（公式、标签、顺序、自定义模板）持久化到 PostgreSQL；保存采用
  **乐观锁（version）**，同工作区并发保存冲突返回 409，互不串写、互不覆盖；
  不同工作区彼此独立。支持 `?ws=<id>` 打开时原样恢复。

## 模块划分

### 后端 `backend/app/`

```
core/
  lexer.py        词法分析：Token + 偏移量/行列，注释处理，永不抛异常
  nodes.py        AST 节点（全部带源码 span）
  parser.py       结构解析：花括号 / \left\right / \begin\end 配对、
                  命令闭合、缺参数/悬空上下标、错误恢复（ErrNode）
  spelling.py     Damerau–Levenshtein 拼写建议（命令与环境）
  renderer.py     AST -> MathML（未解析的 \ref 渲染为醒目 <merror>）
  tolerant.py     好/坏/空片段切分契约 + 容错渲染
  references.py   编号、标签收集/查重、\ref 解析、Tarjan 成环检测与重排
  commands.py     唯一的命令事实表（解析/渲染/建议/符号面板共用）
  service.py      门面：parse_formula / render_formula / preview_workspace
api/
  schemas.py      Pydantic 输入输出契约
  routes.py       /api/parse /render /preview /palette /workspaces
persistence/
  db.py           异步引擎/会话（惰性创建）
  models.py       workspace / formula / custom_template
  repository.py   事务化整工作区写入 + 乐观锁冲突
tests/            编号重排、三类引用异常、错误定位、容错渲染、持久化与 HTTP
main.py           FastAPI 入口（建表、静态托管、CORS）
```

### 前端 `frontend/src/`

```
components/
  CodeEditor.tsx    行号 + 高亮叠加层 + 括号匹配 + 自动补全（命令式插入 API）
  highlight.ts      仅用于着色的前端词法（正确性以后端为准）
  PreviewPane.tsx   挂载后端 MathML，显示编号与错误/引用问题
  FormulaList.tsx   公式列表、标签、拖拽排序、问题角标
  SymbolPanel.tsx   分类符号面板 + 最近使用
  TemplatePanel.tsx 内置/自定义公式模板库
  Splitter.tsx      可拖动两栏分隔条
api/                types.ts（契约）+ client.ts（fetch 封装，409 处理）
hooks/useDebounced.ts  150ms 防抖
data/palette.ts     离线符号骨架 + 内置模板
App.tsx             状态编排（公式/标签/顺序、防抖预览、持久化、冲突提示）
```

## HTTP 契约摘要

- `POST /api/parse`  `{source}` → `{ok, errors:[{code,message,offset,length,
  line,column,suggestion}]}`
- `POST /api/render` `{source, tolerant, refs?}` → 增加 `mathml` 与
  `segments:[{kind:ok|error|blank,start,end,text}]`
- `POST /api/preview` `{formulas:[{clientId,source,label?}], tolerant}` →
  每个公式的 `number/mathml/parseErrors/segments/references` 以及工作区级
  `issues:[{code,message,formulaId,label,line,column,cycle}]`
- `GET/POST /api/workspaces`、`GET/PUT/DELETE /api/workspaces/{id}`
  （PUT 必须带 `expectedVersion`，过期返回 409 + `currentVersion`）
- `GET /api/palette` 由后端命令事实表导出的符号目录
