import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import CodeEditor from "./components/CodeEditor.jsx";
import Preview from "./components/Preview.jsx";
import SymbolPanel from "./components/SymbolPanel.jsx";
import TemplatePanel from "./components/TemplatePanel.jsx";
import FormulaList from "./components/FormulaList.jsx";
import SplitPane from "./components/SplitPane.jsx";
import { analyze, workspacesApi } from "./api.js";

const RENDER_DEBOUNCE_MS = 150;   // 停止输入 150ms 后才请求后端渲染
const SAVE_DEBOUNCE_MS = 1000;

function newFormula(index) {
  return { id: `f_${Date.now().toString(36)}_${index}_${Math.random().toString(36).slice(2, 7)}`,
           source: "", label: "" };
}

export default function App() {
  const [workspaceId, setWorkspaceId] = useState(null);
  const [workspaceName, setWorkspaceName] = useState("未命名工作区");
  const [version, setVersion] = useState(0);
  const [formulas, setFormulas] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [tolerant, setTolerant] = useState(true);
  const [bottomTab, setBottomTab] = useState("symbols"); // symbols | templates
  const [bottomOpen, setBottomOpen] = useState(true);
  const [saveState, setSaveState] = useState("idle"); // idle | saving | saved | conflict
  const [conflictMessage, setConflictMessage] = useState("");
  const [wsList, setWsList] = useState([]);
  const [analyzeError, setAnalyzeError] = useState("");

  const editorRef = useRef(null);
  const renderTimer = useRef(null);
  const saveTimer = useRef(null);
  const skipSaveOnce = useRef(false);

  const active = formulas.find((f) => f.id === activeId) || formulas[0];
  const resultsById = useMemo(() => {
    const m = new Map();
    (analysis?.formulas || []).forEach((r) => m.set(r.id, r));
    return m;
  }, [analysis]);
  const activeResult = active ? resultsById.get(active.id) : null;

  // ---------------------------------------------------------- 首次加载
  const refreshWsList = useCallback(async () => {
    try {
      setWsList(await workspacesApi.list());
    } catch { /* 后端未就绪时忽略 */ }
  }, []);

  const loadWorkspace = useCallback(async (id) => {
    const ws = await workspacesApi.get(id);
    setWorkspaceId(ws.id);
    setWorkspaceName(ws.name);
    setVersion(ws.version);
    setFormulas(ws.formulas);
    setTemplates(ws.templates || []);
    setActiveId(ws.formulas[0]?.id || null);
    setSaveState("idle");
    skipSaveOnce.current = true;
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      await refreshWsList();
      const listed = await workspacesApi.list().catch(() => []);
      if (cancelled) return;
      if (listed.length > 0) {
        await loadWorkspace(listed[0].id);
      } else {
        // 首次：创建一个带示例公式的工作区
        const ws = await workspacesApi.create({
          name: "我的第一个工作区",
          formulas: [
            { id: "demo-1", source: "E = mc^2 \\label{eq:energy}", label: "" },
            { id: "demo-2", source: "由式 \\eqref{eq:energy} 可知能量与质量等价", label: "" },
          ],
        });
        if (cancelled) return;
        setWorkspaceId(ws.id);
        setWorkspaceName(ws.name);
        setVersion(ws.version);
        setFormulas(ws.formulas);
        setActiveId("demo-1");
        await refreshWsList();
      }
    })();
    return () => { cancelled = true; };
  }, [loadWorkspace, refreshWsList]);

  // ------------------------------------------- 150ms 防抖：变化即重新分析
  const scheduleAnalyze = useCallback(() => {
    if (renderTimer.current) clearTimeout(renderTimer.current);
    renderTimer.current = setTimeout(async () => {
      if (formulas.length === 0) {
        setAnalysis(null);
        return;
      }
      try {
        const result = await analyze(formulas, { tolerant });
        setAnalysis(result);
        setAnalyzeError("");
      } catch (err) {
        setAnalyzeError(err.message);
      }
    }, RENDER_DEBOUNCE_MS);
  }, [formulas, tolerant]);

  // formulas/tolerant 变化即重新分析（内部 150ms 防抖）；初次空列表不请求
  useEffect(() => {
    scheduleAnalyze();
  }, [formulas, tolerant, scheduleAnalyze]);

  // ------------------------------------------- 1s 防抖：自动保存（乐观锁）
  const persist = useCallback(async () => {
    if (!workspaceId) return;
    if (skipSaveOnce.current) {
      // 刚从服务器加载完的数据不再回存
      skipSaveOnce.current = false;
      return;
    }
    setSaveState("saving");
    try {
      const saved = await workspacesApi.save(workspaceId, {
        name: workspaceName,
        formulas,
        templates,
        expected_version: version,
      });
      setVersion(saved.version);
      setSaveState("saved");
      setConflictMessage("");
      refreshWsList();
    } catch (err) {
      if (err.status === 409) {
        setSaveState("conflict");
        setConflictMessage(err.message);
      } else {
        setSaveState("error");
      }
    }
  }, [workspaceId, workspaceName, formulas, templates, version, refreshWsList]);

  useEffect(() => {
    if (!workspaceId) return;
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(persist, SAVE_DEBOUNCE_MS);
    return () => saveTimer.current && clearTimeout(saveTimer.current);
  }, [formulas, templates, workspaceName, workspaceId, persist]);

  // ------------------------------------------------------------- 编辑操作
  const updateFormula = (id, patch) => {
    skipSaveOnce.current = false;
    setFormulas((prev) => prev.map((f) => (f.id === id ? { ...f, ...patch } : f)));
  };

  const addFormula = async () => {
    skipSaveOnce.current = false;
    const f = newFormula(formulas.length);
    setFormulas((prev) => [...prev, f]);
    setActiveId(f.id);
  };

  const removeFormula = (id) => {
    skipSaveOnce.current = false;
    setFormulas((prev) => {
      const next = prev.filter((f) => f.id !== id);
      if (activeId === id) setActiveId(next[0]?.id || null);
      return next;
    });
  };

  const reorder = (nextList) => {
    skipSaveOnce.current = false;
    setFormulas(nextList); // 顺序变化 -> 自动触发后端重新编号与引用重排
  };

  const insertAtCursor = (text, selectPlaceholder) => {
    if (!active || !editorRef.current) return;
    editorRef.current.insertAtCursor(text, selectPlaceholder);
  };

  const createNewWorkspace = async () => {
    const ws = await workspacesApi.create({ name: "新工作区", formulas: [] });
    await refreshWsList();
    await loadWorkspace(ws.id);
  };

  const saveStatus = {
    idle: "",
    saving: "保存中…",
    saved: "已保存",
    conflict: "保存冲突",
    error: "保存失败",
  }[saveState];

  return (
    <div className="app">
      <header className="topbar">
        <span className="brand">∑ LaTeX 数学公式编辑器</span>
        <select
          className="workspace-select"
          value={workspaceId || ""}
          onChange={(e) => e.target.value && loadWorkspace(e.target.value)}
        >
          {wsList.map((w) => (
            <option key={w.id} value={w.id}>{w.name}（v{w.version}）</option>
          ))}
        </select>
        <input
          className="workspace-name"
          value={workspaceName}
          onChange={(e) => {
            skipSaveOnce.current = false;
            setWorkspaceName(e.target.value);
          }}
        />
        <button className="btn" onClick={createNewWorkspace}>新建工作区</button>
        <span className={`save-state ${saveState}`}>
          {saveStatus}
          <span className="version-tag">v{version}</span>
        </span>
      </header>

      {saveState === "conflict" && (
        <div className="conflict-banner">
          ⚠ {conflictMessage}
          <button className="btn small" onClick={() => loadWorkspace(workspaceId)}>
            重新加载（放弃本地改动）
          </button>
          <button className="btn small" onClick={() => setSaveState("idle")}>
            我先手动合并
          </button>
        </div>
      )}
      {analyzeError && <div className="conflict-banner error">后端分析失败：{analyzeError}</div>}

      <div className="main-area">
        <aside className="sidebar">
          <div className="sidebar-title">工作区公式（拖动手柄重排编号）</div>
          <FormulaList
            formulas={formulas}
            resultsById={resultsById}
            activeId={active?.id}
            onSelect={setActiveId}
            onReorder={reorder}
            onAdd={addFormula}
            onRemove={removeFormula}
            onLabelChange={(id, label) => updateFormula(id, { label })}
          />
        </aside>

        <div className="workbench">
          <SplitPane
            left={
              active ? (
                <div className="pane-source">
                  <div className="pane-header">
                    <span>公式 #{activeResult?.number ?? ""}</span>
                    {activeResult?.label && (
                      <span className="tag-label">\\label 或标签：{activeResult.label}</span>
                    )}
                  </div>
                  <CodeEditor
                    key={active.id}
                    value={active.source}
                    onChange={(v) => updateFormula(active.id, { source: v })}
                    errors={activeResult?.structure?.errors || []}
                    editorRef={editorRef}
                  />
                </div>
              ) : <div className="empty-hint">还没有公式，点击“新建公式”开始</div>
            }
            right={
              <Preview
                result={activeResult}
                tolerant={tolerant}
                onToggleTolerant={setTolerant}
              />
            }
          />

          {bottomOpen && (
            <div className="bottom-panel">
              <div className="bottom-tabs">
                <button
                  className={bottomTab === "symbols" ? "active" : ""}
                  onClick={() => setBottomTab("symbols")}
                >符号面板</button>
                <button
                  className={bottomTab === "templates" ? "active" : ""}
                  onClick={() => setBottomTab("templates")}
                >公式模板库</button>
              </div>
              {bottomTab === "symbols"
                ? <SymbolPanel onInsert={insertAtCursor} />
                : <TemplatePanel onInsert={insertAtCursor} customTemplates={templates} />}
            </div>
          )}
          <button
            className="collapse-toggle"
            onClick={() => setBottomOpen((v) => !v)}
          >
            {bottomOpen ? "▼ 收起符号/模板面板" : "▲ 展开符号/模板面板"}
          </button>
        </div>
      </div>
    </div>
  );
}
