// Type definitions mirroring the FastAPI response contracts.

export interface Formula {
  clientId: string;
  source: string;
  label?: string | null;
}

export interface CustomTemplate {
  name: string;
  code: string;
  category: string;
}

export interface Workspace {
  id: string;
  name: string;
  version: number;
  createdAt?: string | null;
  updatedAt?: string | null;
  formulas: Formula[];
  templates: CustomTemplate[];
}

export interface ParseErrorInfo {
  code: string;
  message: string;
  offset: number;
  length: number;
  line: number;
  column: number;
  suggestion?: string | null;
}

export interface Segment {
  kind: "ok" | "error" | "blank";
  start: number;
  end: number;
  text: string;
}

export interface ReferenceInfo {
  label: string;
  line: number;
  column: number;
  number: number | null;
  resolved: boolean;
}

export interface PreviewFormula {
  clientId: string;
  number: number;
  label: string | null;
  mathml: string | null;
  parseErrors: ParseErrorInfo[];
  segments: Segment[];
  references: ReferenceInfo[];
}

export interface RefIssue {
  code: "undefined_label" | "duplicate_label" | "reference_cycle";
  message: string;
  formulaId: string;
  label?: string | null;
  offset?: number | null;
  line?: number | null;
  column?: number | null;
  cycle?: string[] | null;
}

export interface PreviewResponse {
  ok: boolean;
  tolerant: boolean;
  formulas: PreviewFormula[];
  issues: RefIssue[];
}

export interface PaletteItem {
  command: string;
  symbol: string;
}

export interface PaletteCategory {
  key: string;
  label: string;
  items: PaletteItem[];
}

export interface RenderResponse {
  ok: boolean;
  errors: ParseErrorInfo[];
  mathml: string | null;
  segments: Segment[];
}
