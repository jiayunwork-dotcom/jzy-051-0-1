import { useMemo, useState } from "react";
import type { PaletteCategory } from "../api/types";
import { FALLBACK_PALETTE } from "../data/palette";

interface Props {
  categories: PaletteCategory[];
  recent: string[];
  collapsed: boolean;
  onToggle: () => void;
  onInsert: (command: string) => void;
}

// Merge backend categories with the static template categories (matrix /
// structures only exist in the static fallback list).
function useMerged(remote: PaletteCategory[]): PaletteCategory[] {
  return useMemo(() => {
    if (remote.length === 0) {
      return FALLBACK_PALETTE.map((c) => ({
        key: c.key,
        label: c.label,
        items: c.items,
      }));
    }
    const extras = FALLBACK_PALETTE.filter(
      (c) => c.key === "matrix" || c.key === "structures"
    );
    return [
      ...remote,
      ...extras.map((c) => ({
        key: c.key,
        label: c.label,
        items: c.items,
      })),
    ];
  }, [remote]);
}

export default function SymbolPanel({
  categories,
  recent,
  collapsed,
  onToggle,
  onInsert,
}: Props) {
  const merged = useMerged(categories);
  const [active, setActive] = useState(
    recent.length > 0 ? "recent" : merged[0]?.key ?? "greek"
  );

  const recentItems = useMemo(() => {
    const byCmd = new Map<string, string>();
    for (const cat of merged) {
      for (const it of cat.items) byCmd.set(it.command, it.symbol);
    }
    return recent.map((command) => ({
      command,
      symbol: byCmd.get(command) ?? command,
    }));
  }, [recent, merged]);

  const current =
    active === "recent"
      ? { key: "recent", label: "最近使用", items: recentItems }
      : merged.find((c) => c.key === active) ?? merged[0];

  return (
    <div className={"symbol-panel" + (collapsed ? " collapsed" : "")}>
      <button className="panel-toggle" onClick={onToggle}>
        {collapsed ? "▲ 符号面板" : "▼ 符号面板"}
      </button>
      {!collapsed && (
        <div className="panel-body">
          <div className="panel-tabs">
            <button
              className={"panel-tab" + (active === "recent" ? " active" : "")}
              onClick={() => setActive("recent")}
              disabled={recentItems.length === 0}
            >
              最近
            </button>
            {merged.map((c) => (
              <button
                key={c.key}
                className={"panel-tab" + (active === c.key ? " active" : "")}
                onClick={() => setActive(c.key)}
              >
                {c.label}
              </button>
            ))}
          </div>
          <div className="panel-grid">
            {current?.items.map((it) => (
              <button
                key={it.command}
                className="symbol-btn"
                title={it.command}
                onClick={() => onInsert(it.command)}
              >
                <span className="symbol-glyph">{it.symbol}</span>
                <span className="symbol-cmd">{it.command}</span>
              </button>
            ))}
            {current?.items.length === 0 && (
              <span className="panel-empty">还没有最近使用的符号</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
