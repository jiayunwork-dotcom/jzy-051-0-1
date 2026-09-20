import React, {
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ParseErrorInfo } from "../api/types";
import { matchBrace, offsetToLineCol, tokenizeForHighlight } from "./highlight";

export interface CodeEditorHandle {
  /** Insert text at the caret (replacing a selection) and refocus. */
  insertText: (text: string, select?: [number, number] | null) => void;
  getSelection: () => { start: number; end: number };
  focus: () => void;
}

interface Props {
  value: string;
  onChange: (next: string) => void;
  errors: ParseErrorInfo[];
  onCursorChange?: (pos: number) => void;
  editorRef?: React.Ref<CodeEditorHandle>;
  placeholder?: string;
}

const OPEN_TO_CLOSE: Record<string, string> = {
  "{": "}",
  "(": ")",
  "[": "]",
};

export default function CodeEditor({
  value,
  onChange,
  errors,
  onCursorChange,
  editorRef,
  placeholder,
}: Props) {
  const taRef = useRef<HTMLTextAreaElement | null>(null);
  const gutterRef = useRef<HTMLDivElement | null>(null);
  const [caret, setCaret] = useState(0);

  const spans = useMemo(() => tokenizeForHighlight(value), [value]);
  const pair = useMemo(() => matchBrace(value, caret), [value, caret]);

  const lineCount = useMemo(() => value.split("\n").length, [value]);

  // Error offsets belonging to the *first* line of each error region.
  const errorOffsets = useMemo(() => {
    const set = new Set<number>();
    for (const e of errors) {
      for (let o = e.offset; o < e.offset + Math.max(e.length, 1); o++) {
        set.add(o);
      }
    }
    return set;
  }, [errors]);

  useImperativeHandle(
    editorRef,
    () => ({
      insertText: (text, select = null) => {
        const ta = taRef.current;
        if (!ta) return;
        const start = ta.selectionStart;
        const end = ta.selectionEnd;
        const next = value.slice(0, start) + text + value.slice(end);
        onChange(next);
        requestAnimationFrame(() => {
          ta.focus();
          if (select) {
            ta.setSelectionRange(start + select[0], start + select[1]);
          } else {
            const pos = start + text.length;
            ta.setSelectionRange(pos, pos);
          }
          setCaret(ta.selectionStart);
        });
      },
      getSelection: () => {
        const ta = taRef.current;
        return ta
          ? { start: ta.selectionStart, end: ta.selectionEnd }
          : { start: 0, end: 0 };
      },
      focus: () => taRef.current?.focus(),
    }),
    [value, onChange]
  );

  const syncScroll = useCallback(() => {
    const ta = taRef.current;
    if (ta && gutterRef.current) {
      gutterRef.current.scrollTop = ta.scrollTop;
    }
  }, []);

  useEffect(() => {
    syncScroll();
  }, [value, syncScroll]);

  const emitCursor = () => {
    const ta = taRef.current;
    if (!ta) return;
    setCaret(ta.selectionStart);
    onCursorChange?.(ta.selectionStart);
  };

  // --- auto-close / typing behaviour -------------------------------------

  const handleKeyDown = (ev: React.KeyboardEvent<HTMLTextAreaElement>) => {
    const ta = ev.currentTarget;
    const { selectionStart: s, selectionEnd: e, value: v } = ev.currentTarget;

    if (ev.key in OPEN_TO_CLOSE) {
      ev.preventDefault();
      const closer = OPEN_TO_CLOSE[ev.key];
      if (s !== e) {
        // Wrap the selection.
        const selected = v.slice(s, e);
        const next = v.slice(0, s) + ev.key + selected + closer + v.slice(e);
        onChange(next);
        requestAnimationFrame(() => {
          ta.setSelectionRange(s + 1, e + 1);
        });
      } else {
        const next = v.slice(0, s) + ev.key + closer + v.slice(e);
        onChange(next);
        requestAnimationFrame(() => ta.setSelectionRange(s + 1, s + 1));
      }
      return;
    }

    // Type the closer over an auto-inserted one.
    if (ev.key === "}" || ev.key === ")" || ev.key === "]") {
      if (s === e && v[s] === ev.key) {
        ev.preventDefault();
        onChange(v.slice(0, s) + v.slice(s + 1));
        requestAnimationFrame(() => ta.setSelectionRange(s + 1, s + 1));
      }
      return;
    }

    // Tab inserts two spaces.
    if (ev.key === "Tab") {
      ev.preventDefault();
      const next = v.slice(0, s) + "  " + v.slice(e);
      onChange(next);
      requestAnimationFrame(() => ta.setSelectionRange(s + 2, s + 2));
    }
  };

  // --- highlighted overlay rendering ------------------------------------

  const highlighted = useMemo(() => {
    const out: React.ReactNode[] = [];
    let pos = 0;
    const push = (start: number, end: number, cls?: string) => {
      if (end <= start) return;
      let text = value.slice(start, end);
      text = text.replace(/\n$/, "\n" + "​");
      out.push(
        <span key={`${start}-${cls ?? "plain"}`} className={cls}>
          {text}
        </span>
      );
    };

    for (const sp of spans) {
      if (sp.start > pos) push(pos, sp.start);
      let cls: string = sp.cls;
      // brace match / error decoration
      if ((sp.cls === "tok-brace") && pair && (sp.start === pair[0] || sp.start === pair[1])) {
        cls += " brace-match";
      }
      if (errorOffsets.has(sp.start)) cls += " token-error";
      push(sp.start, sp.end, cls);
      pos = sp.end;
    }
    if (pos < value.length) push(pos, value.length);
    if (value.length === 0) {
      out.push(<span key="ph" className="placeholder-text">{placeholder ?? ""}</span>);
    }
    return out;
  }, [spans, value, pair, errorOffsets, placeholder]);

  // Lines containing an error get a red marker in the gutter.
  const errorLines = useMemo(() => {
    const set = new Set<number>();
    for (const e of errors) {
      set.add(e.line - 1);
      const end = offsetToLineCol(value, Math.min(e.offset + e.length, value.length));
      for (let l = e.line - 1; l <= end.line; l++) set.add(l);
    }
    return set;
  }, [errors, value]);

  return (
    <div className="code-editor">
      <div className="gutter" ref={gutterRef} aria-hidden>
        {Array.from({ length: lineCount }, (_, i) => (
          <div
            key={i}
            className={"gutter-line" + (errorLines.has(i) ? " has-error" : "")}
          >
            {i + 1}
          </div>
        ))}
      </div>
      <div className="editor-stack">
        <pre className="highlight-layer" aria-hidden>
          <code>{highlighted}</code>
        </pre>
        <textarea
          ref={taRef}
          className="code-input"
          value={value}
          spellCheck={false}
          onChange={(ev) => onChange(ev.target.value)}
          onKeyDown={handleKeyDown}
          onKeyUp={emitCursor}
          onClick={emitCursor}
          onSelect={emitCursor}
          onScroll={syncScroll}
        />
      </div>
    </div>
  );
}
