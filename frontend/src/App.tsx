import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api/client";
import type {
  CustomTemplate,
  Formula,
  PaletteCategory,
  PreviewResponse,
  Workspace,
} from "./api/types";
import CodeEditor, { type CodeEditorHandle } from "./components/CodeEditor";
import FormulaList, {
  type FormulaListItem,
} from "./components/FormulaList";
import PreviewPane from "./components/PreviewPane";
import Splitter from "./components/Splitter";
import SymbolPanel from "./components/SymbolPanel";
import TemplatePanel from "./components/TemplatePanel";
import { useDebounced } from "./hooks/useDebounced";

const RECENT_KEY = "latex-editor.recent-symbols";
const RECENT_LIMIT = 24;

function newClientId(): string {
  return `f-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function loadRecent(): string[] {
  try {
    return JSON.parse(localStorage.getItem(RECENT_KEY) ?? "[]");
  } catch {
    return [];
  }
}

export default function App() {
  const [workspaceId, setWorkspaceId] = useState<string | null>(null);
  const [workspaceName, setWorkspaceName] = useState("未命名工作区");
  const [version, setVersion] = useState(0);
  const [formulas, setFormulas] = useState<Formula[]>([
    { clientId: newClientId(), source: "", label: null },
  ]);
  const [activeId, setActiveId] = useState<string>(formulas[0].clientId);
  const [templates, setTemplates] = useState<CustomTemplate[]>([]);

  const [palette, setPalette] = useState<PaletteCategory[]>([]);
  const [recent, setRecent] = useState<string[]>(loadRecent);
  const [panelCollapsed, setPanelCollapsed] = useState(false);
  const [ratio, setRatio] = useState(0.5);

  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [saveState, setSaveState] = useState<
    { kind: "idle" } | { kind: "saving" } | { kind: "ok" } | { kind: "error"; message: string }
  >({ kind: "idle" });
  const [loadedId, setLoadedId] = useState<string | null>(null);

  const editorRef = useRef<CodeEditorHandle | null>(null);

  // Debounce the *whole* workspace payload; after 150ms idle the backend
  // renumbers everything and re-resolves references.
  const debouncedFormulas = useDebounced(formulas, 150);

  const active = formulas.find((f) => f.clientId === activeId) ?? formulas[0];

  // Load palette once.
  useEffect(() => {
    api
      .palette()
      .then((p) => setPalette(p.categories))
      .catch(() => setPalette([]));
  }, []);

  // Re-preview whenever the debounced source changes.
  useEffect(() => {
    if (debouncedFormulas.length === 0) {
      setPreview(null);
      return;
    }
    let cancelled = false;
    setPreviewLoading(true);
    api
      .preview(debouncedFormulas, true)
      .then((res) => {
        if (!cancelled) setPreview(res);
      })
      .catch(() => {
        if (!cancelled) setPreview(null);
      })
      .finally(() => {
        if (!cancelled) setPreviewLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [debouncedFormulas]);

  const previewById = useMemo(() => {
    const m = new Map(preview?.formulas.map((f) => [f.clientId, f]));
    return m;
  }, [preview]);

  const activePreview = active ? previewById.get(active.clientId) : undefined;
  const activeIssues = useMemo(
    () => preview?.issues.filter((i) => i.formulaId === active?.clientId) ?? [],
    [preview, active]
  );

  // --- formula mutations -------------------------------------------------

  const updateActive = useCallback(
    (patch: Partial<Formula>) => {
      setFormulas((fs) =>
        fs.map((f) => (f.clientId === activeId ? { ...f, ...patch } : f))
      );
    },
    [activeId]
  );

  const addFormula = () => {
    const f: Formula = { clientId: newClientId(), source: "", label: null };
    setFormulas((fs) => [...fs, f]);
    setActiveId(f.clientId);
    editorRef.current?.focus();
  };

  const deleteFormula = (id: string) => {
    setFormulas((fs) => {
      const next = fs.filter((f) => f.clientId !== id);
      if (id === activeId && next.length > 0) setActiveId(next[0].clientId);
      return next;
    });
  };

  // Drag reorder: move `fromId` to the position of `toId`.
  const reorder = (fromId: string, toId: string) => {
    setFormulas((fs) => {
      const from = fs.findIndex((f) => f.clientId === fromId);
      const to = fs.findIndex((f) => f.clientId === toId);
      if (from < 0 || to < 0 || from === to) return fs;
      const next = [...fs];
      const [moved] = next.splice(from, 1);
      next.splice(to, 0, moved);
      return next;
    });
  };

  // --- insertion from panels --------------------------------------------

  const recordRecent = useCallback((command: string) => {
    setRecent((r) => {
      const next = [command, ...r.filter((c) => c !== command)].slice(
        0,
        RECENT_LIMIT
      );
      localStorage.setItem(RECENT_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  const insertCommand = useCallback(
    (command: string) => {
      if (!active) return;
      recordRecent(command);
      // If the snippet contains a placeholder like {分子}, select the first
      // placeholder region after insertion so the user can type over it.
      const ph = command.match(/[一-鿿]+|被开方|分子|分母|上标|下标|条件|否则|表达式|文本|label/);
      const select: [number, number] | null = ph
        ? [ph.index!, ph.index! + ph[0].length]
        : null;
      editorRef.current?.insertText(command, select);
    },
    [active, recordRecent]
  );

  // --- persistence -------------------------------------------------------

  const persist = useCallback(
    async (mode: "create" | "save") => {
      setSaveState({ kind: "saving" });
      try {
        let ws: Workspace;
        if (mode === "create" || !workspaceId) {
          ws = await api.createWorkspace(
            workspaceName,
            formulas,
            templates
          );
        } else {
          ws = await api.saveWorkspace(
            workspaceId,
            workspaceName,
            version,
            formulas,
            templates
          );
        }
        setWorkspaceId(ws.id);
        setVersion(ws.version);
        setLoadedId(ws.id);
        setSaveState({ kind: "ok" });
        window.setTimeout(() => setSaveState({ kind: "idle" }), 1500);
      } catch (e) {
        const err = e as Error & { status?: number; currentVersion?: number };
        if (err.status === 409) {
          setSaveState({
            kind: "error",
            message:
              `${err.message} 若要以当前内容覆盖，请先重新载入该工作区再保存。`,
          });
        } else {
          setSaveState({ kind: "error", message: err.message });
        }
      }
    },
    [workspaceId, workspaceName, version, formulas, templates]
  );

  // Optional: restore a workspace by id from the URL (?ws=<id>).
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get("ws");
    if (!id) return;
    api
      .getWorkspace(id)
      .then((ws) => {
        setWorkspaceId(ws.id);
        setWorkspaceName(ws.name);
        setVersion(ws.version);
        setTemplates(ws.templates);
        setFormulas(
          ws.formulas.length > 0
            ? ws.formulas.map((f) => ({
                clientId: f.clientId,
                source: f.source,
                label: f.label ?? null,
              }))
            : [{ clientId: newClientId(), source: "", label: null }]
        );
        setLoadedId(ws.id);
        if (ws.formulas[0]) setActiveId(ws.formulas[0].clientId);
      })
      .catch(() => undefined);
  }, []);

  const sidebarItems: FormulaListItem[] = (preview?.formulas ?? []).map(
    (f) => ({
      clientId: f.clientId,
      source:
        formulas.find((x) => x.clientId === f.clientId)?.source ?? "",
      label: f.label,
      number: f.number,
      hasParseError: f.parseErrors.length > 0,
    })
  );

  return (
    <div className="app">
      <header className="topbar">
        <input
          className="workspace-name"
          value={workspaceName}
          onChange={(e) => setWorkspaceName(e.target.value)}
          placeholder="工作区名称"
        />
        {loadedId && <span className="ws-id" title={loadedId}>#{loadedId.slice(0, 8)}</span>}
        <div className="topbar-spacer" />
        <span className="save-hint">
          {saveState.kind === "saving" && "保存中…"}
          {saveState.kind === "ok" && "已保存 ✓"}
          {saveState.kind === "error" && (
            <span className="save-error">{saveState.message}</span>
          )}
        </span>
        <button className="btn" onClick={() => persist("create")}>
          另存为新工作区
        </button>
        <button
          className="btn btn-primary"
          onClick={() => persist("save")}
          disabled={saveState.kind === "saving"}
        >
          保存
        </button>
      </header>

      <div className="main">
        <FormulaList
          formulas={
            sidebarItems.length > 0
              ? sidebarItems
              : formulas.map((f, i) => ({
                  clientId: f.clientId,
                  source: f.source,
                  label: f.label ?? null,
                  number: i + 1,
                  hasParseError: false,
                }))
          }
          activeId={active?.clientId ?? ""}
          issues={preview?.issues ?? []}
          onSelect={setActiveId}
          onAdd={addFormula}
          onDelete={deleteFormula}
          onReorder={reorder}
        />

        <section className="workbench">
          <div className="formula-meta">
            <span className="formula-meta-number">
              公式 #{activePreview?.number ?? "-"}
            </span>
            <input
              className="label-input"
              value={active?.label ?? ""}
              placeholder="可选标签（用于 \\ref{标签} 交叉引用）"
              onChange={(e) =>
                updateActive({ label: e.target.value || null })
              }
            />
          </div>

          <div className="split-container">
            <div className="pane pane-left" style={{ width: `${ratio * 100}%` }}>
              <CodeEditor
                editorRef={editorRef}
                value={active?.source ?? ""}
                onChange={(src) => updateActive({ source: src })}
                errors={activePreview?.parseErrors ?? []}
                placeholder={"在此输入 LaTeX，例如 \\frac{a}{b}…"}
              />
            </div>
            <Splitter ratio={ratio} onChange={setRatio} />
            <div
              className="pane pane-right"
              style={{ width: `${(1 - ratio) * 100}%` }}
            >
              <PreviewPane
                number={activePreview?.number ?? null}
                label={activePreview?.label ?? null}
                mathml={activePreview?.mathml ?? null}
                parseErrors={activePreview?.parseErrors ?? []}
                issues={activeIssues}
                loading={previewLoading}
              />
            </div>
          </div>

          <TemplatePanel
            custom={templates}
            onInsert={insertCommand}
            onSaveTemplate={(t) =>
              setTemplates((ts) => [...ts.filter((x) => x.name !== t.name), t])
            }
          />

          <SymbolPanel
            categories={palette}
            recent={recent}
            collapsed={panelCollapsed}
            onToggle={() => setPanelCollapsed((v) => !v)}
            onInsert={insertCommand}
          />
        </section>
      </div>
    </div>
  );
}
