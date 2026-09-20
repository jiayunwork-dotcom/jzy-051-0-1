import { useEffect, useMemo, useRef, useState, useImperativeHandle, useCallback } from "react";

// 前端词法切分仅用于外观高亮；权威解析以后端 /api/parse 为准。
const RE_COMMAND = /\\[a-zA-Z]+|\\./y;
const RE_COMMENT = /%[^\n]*/y;
const RE_NUMBER = /\d+(?:\.\d+)?/y;
const RE_WORD = /[A-Za-z]+/y;
const RE_SPACE = /[ \t\r]+/y;

const SYMBOL_CHARS = new Set("+-=<>≤≥≠≈±×÷√∞∂∇∈∉⊂⊃⊆⊇∪∩∧∨¬∀∃∑∏∫∮·…→←↔⇒⇐⇔↦|/");

function escapeHtml(s) {
  return s.replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]),
  );
}

// 返回带高亮 span 的 HTML
function highlight(source) {
  let out = "";
  let i = 0;
  const push = (cls, text) => {
    if (!text) return;
    out += cls
      ? `<span class="tok-${cls}">${escapeHtml(text)}</span>`
      : escapeHtml(text);
  };
  while (i < source.length) {
    const ch = source[i];
    if (ch === "\n") { out += "\n"; i += 1; continue; }
    RE_SPACE.lastIndex = i;
    let m = RE_SPACE.exec(source);
    if (m) { i = RE_SPACE.lastIndex; continue; }

    RE_COMMENT.lastIndex = i;
    m = RE_COMMENT.exec(source);
    if (m) { push("comment", m[0]); i = RE_COMMENT.lastIndex; continue; }

    RE_COMMAND.lastIndex = i;
    m = RE_COMMAND.exec(source);
    if (m) { push("command", m[0]); i = RE_COMMAND.lastIndex; continue; }

    if (ch === "{" || ch === "}") { push("brace", ch); i += 1; continue; }
    if (ch === "[" || ch === "]" || ch === "(" || ch === ")") {
      push("bracket", ch); i += 1; continue;
    }
    if (ch === "^" || ch === "_" || ch === "&") {
      push("accent", ch); i += 1; continue;
    }
    RE_NUMBER.lastIndex = i;
    m = RE_NUMBER.exec(source);
    if (m) { push("number", m[0]); i = RE_NUMBER.lastIndex; continue; }

    RE_WORD.lastIndex = i;
    m = RE_WORD.exec(source);
    if (m) { push("word", m[0]); i = RE_WORD.lastIndex; continue; }

    if (SYMBOL_CHARS.has(ch)) { push("symbol", ch); i += 1; continue; }
    push(null, ch);
    i += 1;
  }
  return out;
}

// 在 source 中找光标处括号的配对偏移（花括号优先，方/圆括号次之）
function findMatch(source, pos) {
  const pairs = { "{": "}", "}": "{", "[": "]", "]": "[", "(": ")", ")": "(" };
  const opens = new Set(["{", "[", "("]);
  const closes = new Set(["}", "]", ")"]);
  const before = source[pos - 1];
  const at = source[pos];
  let openCh = null;
  let start = -1;
  let forward = false;
  if (before && (opens.has(before) || closes.has(before))) {
    if (opens.has(before)) { openCh = before; start = pos - 1; forward = true; }
  }
  if (openCh === null && at && opens.has(at)) {
    openCh = at; start = pos; forward = true;
  }
  if (openCh === null && at && closes.has(at)) {
    // 从闭括号向左找
    const target = pairs[at];
    let depth = 0;
    for (let k = pos; k >= 0; k -= 1) {
      const c = source[k];
      if (c === at) depth += 1;
      else if (c === target) {
        depth -= 1;
        if (depth === 0) return { open: k, close: pos };
      }
    }
    return null;
  }
  if (openCh === null) return null;
  const closeCh = pairs[openCh];
  let depth = 0;
  for (let k = start; k < source.length; k += 1) {
    const c = source[k];
    if (c === openCh) depth += 1;
    else if (c === closeCh) {
      depth -= 1;
      if (depth === 0) {
        return forward
          ? { open: start, close: k }
          : { open: k, close: start };
      }
    }
  }
  return null;
}

const AUTO_CLOSE = { "{": "}", "[": "]", "(": ")" };

const CodeEditor = ({ value, onChange, errors = [], editorRef }) => {
  const taRef = useRef(null);
  const gutterRef = useRef(null);
  const highlightRef = useRef(null);
  const [cursor, setCursor] = useState(0);
  const [match, setMatch] = useState(null);

  useImperativeHandle(editorRef, () => ({
    insertAtCursor(text, selections) {
      const ta = taRef.current;
      if (!ta) return;
      const start = ta.selectionStart;
      const end = ta.selectionEnd;
      const next = value.slice(0, start) + text + value.slice(end);
      onChange(next);
      requestAnimationFrame(() => {
        ta.focus();
        if (selections && selections.length) {
          // 选中第一个 {} 占位参数：找到 start 之后的第一个 "{}"
          const anchor = next.indexOf("{}", start);
          if (anchor !== -1) {
            ta.setSelectionRange(anchor + 1, anchor + 1);
            return;
          }
        }
        ta.setSelectionRange(start + text.length, start + text.length);
      });
    },
    focus() {
      taRef.current?.focus();
    },
    goToOffset(offset) {
      const ta = taRef.current;
      if (!ta) return;
      ta.focus();
      ta.setSelectionRange(offset, offset);
      setCursor(offset);
    },
  }));

  const lineCount = useMemo(() => Math.max(1, value.split("\n").length), [value]);

  // 高亮 HTML + 末尾哨兵换行，保证最后一行高度可滚动对齐
  const highlighted = useMemo(() => highlight(value) + "\n", [value]);

  // 光标处括号匹配
  useEffect(() => {
    setMatch(findMatch(value, cursor));
  }, [value, cursor]);

  const syncScroll = useCallback(() => {
    const ta = taRef.current;
    if (!ta) return;
    if (highlightRef.current) {
      highlightRef.current.scrollTop = ta.scrollTop;
      highlightRef.current.scrollLeft = ta.scrollLeft;
    }
    if (gutterRef.current) {
      gutterRef.current.scrollTop = ta.scrollTop;
    }
  }, []);

  const handleKeyDown = (e) => {
    const ta = e.currentTarget;
    // 花括号/括号自动补全
    if (AUTO_CLOSE[e.key]) {
      const s = ta.selectionStart;
      const en = ta.selectionEnd;
      const close = AUTO_CLOSE[e.key];
      if (s !== en) {
        // 包裹选区
        e.preventDefault();
        const sel = value.slice(s, en);
        const next = value.slice(0, s) + e.key + sel + close + value.slice(en);
        onChange(next);
        requestAnimationFrame(() => ta.setSelectionRange(s + 1, en + 1));
        return;
      }
      // 紧邻已存在同类型闭括号时，直接跳过它
      if (value[s] === close) {
        e.preventDefault();
        ta.setSelectionRange(s + 1, s + 1);
        return;
      }
      e.preventDefault();
      const next = value.slice(0, s) + e.key + close + value.slice(s);
      onChange(next);
      requestAnimationFrame(() => ta.setSelectionRange(s + 1, s + 1));
      return;
    }
    if (e.key === "Backspace") {
      const s = ta.selectionStart;
      const en = ta.selectionEnd;
      if (s === en && AUTO_CLOSE[value[s - 1]] &&
          AUTO_CLOSE[value[s - 1]] === value[s]) {
        e.preventDefault();
        const next = value.slice(0, s - 1) + value.slice(s + 1);
        onChange(next);
        requestAnimationFrame(() => ta.setSelectionRange(s - 1, s - 1));
        return;
      }
    }
    // Tab 插入两个空格而非切走焦点
    if (e.key === "Tab") {
      e.preventDefault();
      const s = ta.selectionStart;
      const next = value.slice(0, s) + "  " + value.slice(ta.selectionEnd);
      onChange(next);
      requestAnimationFrame(() => ta.setSelectionRange(s + 2, s + 2));
    }
  };

  // 错误波浪线覆盖层：按行显示（后端给出了 line/column）
  const errorMarkers = errors.map((err, idx) => ({
    key: idx,
    line: err.line,
    column: err.column,
    message: err.message,
    code: err.code,
  }));

  const matchOpenOffset = match?.open;
  const matchCloseOffset = match?.close;

  // 在高亮 HTML 上叠加括号配对高亮：重新渲染时基于偏移插入 class 标记较复杂，
  // 这里用一个独立的透明覆盖层绘制两个小标记。
  const markerPositions = useMemo(() => {
    if (match == null) return null;
    const beforeOpen = value.slice(0, match.open);
    const beforeClose = value.slice(0, match.close);
    const loc = (s) => ({ line: s.split("\n").length, col: s.split("\n").pop().length });
    return { open: loc(beforeOpen), close: loc(beforeClose) };
  }, [match, value]);

  return (
    <div className="code-editor">
      <div className="gutter" ref={gutterRef} aria-hidden="true">
        {Array.from({ length: lineCount }, (_, i) => (
          <div key={i} className="gutter-line">{i + 1}</div>
        ))}
      </div>
      <div className="editor-body">
        <pre
          ref={highlightRef}
          className="highlight-layer"
          aria-hidden="true"
          dangerouslySetInnerHTML={{ __html: highlighted }}
        />
        <div className="error-marker-layer" aria-hidden="true">
          {errorMarkers.map((m) => (
            <div
              key={m.key}
              className="error-line-marker"
              title={`${m.code}: ${m.message}`}
              style={{ top: `calc(${(m.line - 1) * 1.6}em + 4px)` }}
            />
          ))}
          {markerPositions && (
            <>
              <div
                className="brace-match-marker"
                style={{
                  top: `calc(${(markerPositions.open.line - 1) * 1.6}em + 4px)`,
                  left: `calc(${markerPositions.open.col}ch + 8px)`,
                }}
              />
              <div
                className="brace-match-marker"
                style={{
                  top: `calc(${(markerPositions.close.line - 1) * 1.6}em + 4px)`,
                  left: `calc(${markerPositions.close.col}ch + 8px)`,
                }}
              />
            </>
          )}
        </div>
        <textarea
          ref={taRef}
          value={value}
          spellCheck={false}
          onChange={(e) => onChange(e.target.value)}
          onScroll={syncScroll}
          onKeyDown={handleKeyDown}
          onKeyUp={(e) => setCursor(e.currentTarget.selectionStart)}
          onClick={(e) => setCursor(e.currentTarget.selectionStart)}
          onSelect={(e) => setCursor(e.currentTarget.selectionStart)}
          className="editor-textarea"
          placeholder="在此输入 LaTeX 数学公式，例如：\frac{a}{b} + \sqrt{x^2}"
        />
      </div>
    </div>
  );
};

export { highlight, findMatch };
export default CodeEditor;
