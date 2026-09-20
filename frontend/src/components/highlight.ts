// Presentation-only LaTeX highlighter used to color the transparent
// textarea overlay.  This is NOT the correctness lexer — tokenizing,
// pairing and validation for real all happen in the backend kernel.
//
// Output: ordered non-overlapping spans {start,end,cls} covering code runs.

export type TokenClass =
  | "tok-command"
  | "tok-brace"
  | "tok-bracket"
  | "tok-symbol"
  | "tok-comment"
  | "tok-script";

export interface TokenSpan {
  start: number;
  end: number;
  cls: TokenClass;
}

const COMMAND_RE = /\\[a-zA-Z]+|\\[^\s]|\\\\/y;
const COMMENT_RE = /%[^\n]*/y;

const MATH_SYMBOLS = new Set("=+-/*<>≤≥≠≈∈∉⊂⊃∩∪∑∏∫∞∂∇±×÷→←⇒⇔…");

export function tokenizeForHighlight(source: string): TokenSpan[] {
  const spans: TokenSpan[] = [];
  let i = 0;
  const n = source.length;

  const matchAt = (re: RegExp): string | null => {
    re.lastIndex = i;
    const m = re.exec(source);
    return m && m.index === i ? m[0] : null;
  };

  while (i < n) {
    const ch = source[i];

    const comment = matchAt(COMMENT_RE);
    if (comment) {
      spans.push({ start: i, end: i + comment.length, cls: "tok-comment" });
      i += comment.length;
      continue;
    }

    const cmd = matchAt(COMMAND_RE);
    if (cmd) {
      spans.push({ start: i, end: i + cmd.length, cls: "tok-command" });
      i += cmd.length;
      continue;
    }

    if (ch === "{" || ch === "}") {
      spans.push({ start: i, end: i + 1, cls: "tok-brace" });
    } else if (ch === "[" || ch === "]") {
      spans.push({ start: i, end: i + 1, cls: "tok-bracket" });
    } else if (ch === "^" || ch === "_") {
      spans.push({ start: i, end: i + 1, cls: "tok-script" });
    } else if (MATH_SYMBOLS.has(ch)) {
      let j = i + 1;
      while (j < n && MATH_SYMBOLS.has(source[j])) j++;
      spans.push({ start: i, end: j, cls: "tok-symbol" });
      i = j;
      continue;
    }
    i += 1;
  }
  return spans;
}

// Bracket matching for the caret position: returns the pair of offsets
// [open, close] of the innermost matching braces, or null.
export function matchBrace(
  source: string,
  caret: number
): [number, number] | null {
  // Try the character just before the caret first, then the one at caret.
  const probes = [caret - 1, caret].filter((p) => p >= 0 && p < source.length);
  for (const p of probes) {
    const ch = source[p];
    if (ch === "{") {
      let depth = 0;
      for (let j = p; j < source.length; j++) {
        if (source[j] === "{") depth++;
        else if (source[j] === "}") {
          depth--;
          if (depth === 0) return [p, j];
        }
      }
    } else if (ch === "}") {
      let depth = 0;
      for (let j = p; j >= 0; j--) {
        if (source[j] === "}") depth++;
        else if (source[j] === "{") {
          depth--;
          if (depth === 0) return [j, p];
        }
      }
    }
  }
  return null;
}

// Convert a flat source offset to {line, column} (0-based lines).
export function offsetToLineCol(
  source: string,
  offset: number
): { line: number; column: number } {
  let line = 0;
  const lastNl = source.lastIndexOf("\n", offset - 1);
  if (lastNl >= 0) line = source.slice(0, offset).split("\n").length - 1;
  return { line, column: offset - lastNl - 1 };
}
