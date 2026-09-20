// 右侧实时预览：只负责呈现后端返回的 HTML（data-URI SVG）与错误信息。
import { useMemo } from "react";

export default function Preview({ result, tolerant, onToggleTolerant }) {
  const structureErrors = result?.structure?.errors || [];
  const xrefErrors = result?.xref_errors || [];
  const html = result?.render?.html || "";
  const fatal = result?.render?.fatal;

  const errorList = useMemo(
    () => [
      ...structureErrors.map((e) => ({
        key: "s" + e.offset + e.code,
        offset: e.offset,
        title: `第 ${e.line} 行第 ${e.column} 列 · ${e.code}`,
        message: e.message,
        suggestion: e.suggestion,
      })),
      ...xrefErrors.map((e) => ({
        key: "x" + e.offset + e.code,
        offset: e.offset,
        title: `第 ${e.line} 行第 ${e.column} 列 · ${e.code}`,
        message: e.message,
      })),
    ],
    [structureErrors, xrefErrors],
  );

  return (
    <div className="preview">
      <div className="preview-toolbar">
        <span className="preview-title">实时预览</span>
        <label className="tolerant-toggle">
          <input
            type="checkbox"
            checked={tolerant}
            onChange={(e) => onToggleTolerant(e.target.checked)}
          />
          容错渲染
        </label>
        {result && (
          <span className={`render-badge ${errorList.length ? "bad" : "good"}`}>
            {errorList.length ? `${errorList.length} 个问题` : "无错误"}
          </span>
        )}
      </div>
      <div className="preview-canvas">
        {result ? (
          <>
            <div
              className="rendered-math"
              dangerouslySetInnerHTML={{ __html: html }}
            />
            {fatal && (
              <div className="fatal-banner">无法渲染该公式：{fatal}</div>
            )}
          </>
        ) : (
          <div className="preview-empty">停止输入 150ms 后将在此渲染…</div>
        )}
      </div>
      <div className="error-panel">
        {errorList.length === 0 ? (
          <div className="error-panel-ok">后端校验通过</div>
        ) : (
          errorList.map((e) => (
            <div key={e.key} className="error-item" data-offset={e.offset}>
              <span className="error-loc">{e.title}</span>
              <span className="error-msg">{e.message}</span>
              {e.suggestion && (
                <span className="error-suggest">建议：\{e.suggestion}</span>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
