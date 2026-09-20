import { useState } from "react";
import { SYMBOL_CATEGORIES, MATRIX_INSERTS } from "../data/symbols.js";

// 最近使用：localStorage 持久化，按使用时间倒序，最多 12 个
const RECENT_KEY = "latex-editor-recent-symbols";

function loadRecent() {
  try {
    return JSON.parse(localStorage.getItem(RECENT_KEY) || "[]");
  } catch {
    return [];
  }
}

export default function SymbolPanel({ onInsert }) {
  const [active, setActive] = useState("greek");
  const [recent, setRecent] = useState(loadRecent);

  const insert = (code) => {
    onInsert(code, code.includes("{}"));
    setRecent((prev) => {
      const next = [code, ...prev.filter((c) => c !== code)].slice(0, 12);
      localStorage.setItem(RECENT_KEY, JSON.stringify(next));
      return next;
    });
  };

  const category = SYMBOL_CATEGORIES.find((c) => c.key === active);

  return (
    <div className="symbol-panel">
      <div className="symbol-tabs">
        {SYMBOL_CATEGORIES.map((c) => (
          <button
            key={c.key}
            className={`symbol-tab ${active === c.key ? "active" : ""}`}
            onClick={() => setActive(c.key)}
          >
            {c.label}
          </button>
        ))}
        <button
          className={`symbol-tab ${active === "matrix" ? "active" : ""}`}
          onClick={() => setActive("matrix")}
        >
          矩阵模板
        </button>
        <button
          className={`symbol-tab ${active === "recent" ? "active" : ""}`}
          onClick={() => setActive("recent")}
        >
          最近使用
        </button>
      </div>
      <div className="symbol-grid">
        {active === "matrix"
          ? MATRIX_INSERTS.map((m) => (
              <button
                key={m.label}
                className="symbol-item matrix-item"
                title={m.code}
                onClick={() => insert(m.code)}
              >
                {m.label}
              </button>
            ))
          : active === "recent"
            ? recent.length
              ? recent.map((code) => (
                  <button
                    key={code}
                    className="symbol-item"
                    title={code}
                    onClick={() => insert(code)}
                  >
                    {code}
                  </button>
                ))
              : <span className="recent-empty">还没有最近使用的符号</span>
            : category.symbols.map((s) => (
                <button
                  key={s.code}
                  className="symbol-item"
                  title={s.code}
                  onClick={() => insert(s.code)}
                >
                  {s.display || s.code}
                </button>
              ))}
      </div>
    </div>
  );
}
