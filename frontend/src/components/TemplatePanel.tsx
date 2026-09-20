import { useMemo, useState } from "react";
import type { CustomTemplate } from "../api/types";
import { FORMULA_TEMPLATES } from "../data/palette";

interface Props {
  custom: CustomTemplate[];
  onInsert: (code: string) => void;
  onSaveTemplate: (t: CustomTemplate) => void;
}

export default function TemplatePanel({
  custom,
  onInsert,
  onSaveTemplate,
}: Props) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [filter, setFilter] = useState<string>("全部");

  const all = useMemo(() => [...custom, ...FORMULA_TEMPLATES], [custom]);
  const categories = useMemo(
    () => ["全部", ...Array.from(new Set(all.map((t) => t.category)))],
    [all]
  );
  const shown = filter === "全部" ? all : all.filter((t) => t.category === filter);

  const save = () => {
    if (!name.trim() || !code.trim()) return;
    onSaveTemplate({ name: name.trim(), code, category: "自定义" });
    setName("");
    setCode("");
    setOpen(false);
  };

  return (
    <div className="template-panel">
      <div className="template-toolbar">
        <span className="template-heading">公式模板库</span>
        <div className="template-filters">
          {categories.map((c) => (
            <button
              key={c}
              className={"chip" + (filter === c ? " active" : "")}
              onClick={() => setFilter(c)}
            >
              {c}
            </button>
          ))}
        </div>
        <button className="btn btn-small" onClick={() => setOpen((v) => !v)}>
          {open ? "取消" : "存为模板"}
        </button>
      </div>

      {open && (
        <div className="template-form">
          <input
            placeholder="模板名称"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <textarea
            placeholder="LaTeX 骨架，例如 \int_{a}^{b} ..."
            value={code}
            onChange={(e) => setCode(e.target.value)}
            rows={2}
          />
          <button className="btn btn-primary" onClick={save}>
            保存
          </button>
        </div>
      )}

      <div className="template-grid">
        {shown.map((t, i) => (
          <button
            key={`${t.name}-${i}`}
            className="template-card"
            title={t.code}
            onClick={() => onInsert(t.code)}
          >
            <span className="template-name">{t.name}</span>
            <code className="template-code">{t.code}</code>
          </button>
        ))}
      </div>
    </div>
  );
}
