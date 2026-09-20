import { useEffect, useRef } from "react";
import type { ParseErrorInfo, RefIssue } from "../api/types";

interface Props {
  number: number | null;
  label: string | null;
  mathml: string | null;
  parseErrors: ParseErrorInfo[];
  issues: RefIssue[];
  loading: boolean;
}

// The backend already turned the source into MathML; the browser only
// mounts it. Unresolved references arrive as <merror class="ref-error">.
export default function PreviewPane({
  number,
  label,
  mathml,
  parseErrors,
  issues,
  loading,
}: Props) {
  const hostRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    if (mathml) {
      host.innerHTML = mathml;
    } else {
      host.replaceChildren();
    }
  }, [mathml]);

  return (
    <div className="preview-pane">
      <div className="preview-header">
        <span className="preview-title">实时预览</span>
        {number !== null && (
          <span className="formula-number" title={label ?? undefined}>
            ({number})
          </span>
        )}
        {loading && <span className="preview-loading">排版中…</span>}
      </div>

      <div className="preview-body">
        <div ref={hostRef} className="mathml-host" />
      </div>

      {(parseErrors.length > 0 || issues.length > 0) && (
        <div className="preview-errors">
          {issues.map((iss, i) => (
            <div key={`iss-${i}`} className={`issue issue-${iss.code}`}>
              <span className="issue-tag">
                {iss.code === "undefined_label"
                  ? "未定义标签"
                  : iss.code === "duplicate_label"
                    ? "重复标签"
                    : "引用成环"}
              </span>
              <span className="issue-msg">{iss.message}</span>
            </div>
          ))}
          {parseErrors.map((e, i) => (
            <div key={`pe-${i}`} className={`issue issue-${e.code}`}>
              <span className="issue-tag">
                {e.line}:{e.column}
              </span>
              <span className="issue-msg">{e.message}</span>
              {e.suggestion && (
                <span className="issue-suggest">建议：{e.suggestion}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
