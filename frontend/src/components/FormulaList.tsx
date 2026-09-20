import { useState } from "react";
import type { RefIssue } from "../api/types";

export interface FormulaListItem {
  clientId: string;
  source: string;
  label: string | null;
  number: number;
  hasParseError: boolean;
}

interface Props {
  formulas: FormulaListItem[];
  activeId: string;
  issues: RefIssue[];
  onSelect: (id: string) => void;
  onAdd: () => void;
  onDelete: (id: string) => void;
  onReorder: (fromId: string, toId: string) => void;
}

export default function FormulaList({
  formulas,
  activeId,
  issues,
  onSelect,
  onAdd,
  onDelete,
  onReorder,
}: Props) {
  const [dragId, setDragId] = useState<string | null>(null);
  const [overId, setOverId] = useState<string | null>(null);

  const issueByFormula = new Map<string, RefIssue[]>();
  for (const iss of issues) {
    const arr = issueByFormula.get(iss.formulaId) ?? [];
    arr.push(iss);
    issueByFormula.set(iss.formulaId, arr);
  }

  return (
    <aside className="formula-list">
      <div className="formula-list-header">
        <span>公式（{formulas.length}）</span>
        <button className="btn btn-small btn-primary" onClick={onAdd}>
          + 新公式
        </button>
      </div>
      <ul>
        {formulas.map((f) => {
          const problems = issueByFormula.get(f.clientId) ?? [];
          const broken = f.hasParseError || problems.length > 0;
          return (
            <li
              key={f.clientId}
              draggable
              className={
                "formula-item" +
                (f.clientId === activeId ? " active" : "") +
                (dragId === f.clientId ? " dragging" : "") +
                (overId === f.clientId && dragId !== f.clientId
                  ? " drop-target"
                  : "")
              }
              onClick={() => onSelect(f.clientId)}
              onDragStart={() => setDragId(f.clientId)}
              onDragEnd={() => {
                setDragId(null);
                setOverId(null);
              }}
              onDragOver={(e) => {
                e.preventDefault();
                if (dragId && dragId !== f.clientId) setOverId(f.clientId);
              }}
              onDrop={(e) => {
                e.preventDefault();
                if (dragId && dragId !== f.clientId) {
                  onReorder(dragId, f.clientId);
                }
                setDragId(null);
                setOverId(null);
              }}
            >
              <span className="drag-handle" title="拖拽排序">
                ⠿
              </span>
              <span className="formula-item-number">({f.number})</span>
              <span className="formula-item-preview">
                {f.source.replace(/\s+/g, " ").trim() || "空公式"}
              </span>
              {f.label && <span className="formula-item-label">{f.label}</span>}
              {broken && (
                <span
                  className="formula-item-warn"
                  title={problems.map((p) => p.message).join("\n")}
                >
                  ⚠
                </span>
              )}
              <button
                className="formula-item-del"
                title="删除公式"
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(f.clientId);
                }}
              >
                ×
              </button>
            </li>
          );
        })}
        {formulas.length === 0 && (
          <li className="formula-empty">还没有公式，点「新公式」开始</li>
        )}
      </ul>
    </aside>
  );
}
