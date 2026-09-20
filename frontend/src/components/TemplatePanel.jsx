import { FORMULA_TEMPLATES } from "../data/symbols.js";

// 公式模板库：点击插入完整骨架
export default function TemplatePanel({ onInsert, customTemplates = [] }) {
  return (
    <div className="template-panel">
      <div className="template-section-title">公式模板库</div>
      <div className="template-grid">
        {FORMULA_TEMPLATES.map((t) => (
          <button
            key={t.key}
            className="template-item"
            title={t.code}
            onClick={() => onInsert(t.code, true)}
          >
            <span className="template-name">{t.name}</span>
            <code className="template-code">{t.code}</code>
          </button>
        ))}
        {customTemplates.map((t, i) => (
          <button
            key={`custom-${i}`}
            className="template-item custom"
            title={t.code}
            onClick={() => onInsert(t.code, true)}
          >
            <span className="template-name">★ {t.name}</span>
            <code className="template-code">{t.code}</code>
          </button>
        ))}
      </div>
    </div>
  );
}
