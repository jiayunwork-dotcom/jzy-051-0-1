// 工作区中的公式列表：展示自动编号、标签，支持拖拽调整顺序、新增、删除。
// 顺序变化后由 App 重新请求后端 /api/analyze，编号与交叉引用全部在后端重排。
import { useState } from "react";

export default function FormulaList({
  formulas,
  resultsById,
  activeId,
  onSelect,
  onReorder,
  onAdd,
  onRemove,
  onLabelChange,
}) {
  const [dragIndex, setDragIndex] = useState(null);
  const [overIndex, setOverIndex] = useState(null);

  const handleDrop = (targetIndex) => {
    if (dragIndex === null || dragIndex === targetIndex) {
      setDragIndex(null);
      setOverIndex(null);
      return;
    }
    const next = [...formulas];
    const [moved] = next.splice(dragIndex, 1);
    next.splice(targetIndex, 0, moved);
    onReorder(next);
    setDragIndex(null);
    setOverIndex(null);
  };

  return (
    <div className="formula-list">
      {formulas.map((f, i) => {
        const r = resultsById.get(f.id);
        const hasError =
            r &&
            ((r.structure && !r.structure.ok) ||
              (r.xref_errors && r.xref_errors.length > 0));
        return (
          <div
            key={f.id}
            className={`formula-row ${activeId === f.id ? "active" : ""} ${
              dragIndex === i ? "dragging" : ""
            } ${overIndex === i && dragIndex !== i ? "over" : ""} ${
              hasError ? "has-error" : ""
            }`}
            draggable
            onDragStart={() => setDragIndex(i)}
            onDragEnter={() => setOverIndex(i)}
            onDragOver={(e) => e.preventDefault()}
            onDragEnd={() => {
              setDragIndex(null);
              setOverIndex(null);
            }}
            onDrop={(e) => {
              e.preventDefault();
              handleDrop(i);
            }}
            onClick={() => onSelect(f.id)}
          >
            <span className="drag-handle" title="拖拽调整编号顺序">⠿</span>
            <span className="formula-number">
              {r ? `(${r.number})` : `(${i + 1})`}
            </span>
            <div className="formula-row-body">
              <input
                className="label-input"
                value={f.label || ""}
                placeholder={labelPlaceholder(f.source)}
                onClick={(e) => e.stopPropagation()}
                onChange={(e) => onLabelChange(f.id, e.target.value)}
                title="可选标签，供 \ref{标签} 交叉引用"
              />
              <code className="formula-snippet">
                {f.source.slice(0, 48) || "（空公式）"}
              </code>
            </div>
            {hasError && <span className="formula-warn" title="存在错误">!</span>}
            <button
              className="formula-del"
              title="删除该公式"
              onClick={(e) => {
                e.stopPropagation();
                onRemove(f.id);
              }}
            >
              ×
            </button>
          </div>
        );
      })}
      <button className="add-formula-btn" onClick={onAdd}>
        ＋ 新建公式
      </button>
    </div>
  );
}

function labelPlaceholder(source) {
  const m = /\\label\s*\{([^}]*)\}/.exec(source || "");
  return m ? `源码内标签：${m[1]}` : "标签（可选，如 eq:energy）";
}
