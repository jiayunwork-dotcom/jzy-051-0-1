// Static fallback palette (the backend /api/palette is the authority and
// overrides this after load) and the built-in formula template library.

import type { CustomTemplate } from "../api/types";

export interface SymbolCategory {
  key: string;
  label: string;
  items: { command: string; symbol: string }[];
}

export const FALLBACK_PALETTE: SymbolCategory[] = [
  {
    key: "greek",
    label: "希腊字母",
    items: [
      { command: "\\alpha", symbol: "α" },
      { command: "\\beta", symbol: "β" },
      { command: "\\gamma", symbol: "γ" },
      { command: "\\delta", symbol: "δ" },
      { command: "\\epsilon", symbol: "ϵ" },
      { command: "\\varepsilon", symbol: "ε" },
      { command: "\\zeta", symbol: "ζ" },
      { command: "\\eta", symbol: "η" },
      { command: "\\theta", symbol: "θ" },
      { command: "\\lambda", symbol: "λ" },
      { command: "\\mu", symbol: "μ" },
      { command: "\\pi", symbol: "π" },
      { command: "\\sigma", symbol: "σ" },
      { command: "\\phi", symbol: "ϕ" },
      { command: "\\varphi", symbol: "φ" },
      { command: "\\omega", symbol: "ω" },
      { command: "\\Gamma", symbol: "Γ" },
      { command: "\\Delta", symbol: "Δ" },
      { command: "\\Theta", symbol: "Θ" },
      { command: "\\Sigma", symbol: "Σ" },
      { command: "\\Omega", symbol: "Ω" },
    ],
  },
  {
    key: "operators",
    label: "运算符",
    items: [
      { command: "\\pm", symbol: "±" },
      { command: "\\times", symbol: "×" },
      { command: "\\div", symbol: "÷" },
      { command: "\\cdot", symbol: "⋅" },
      { command: "\\cap", symbol: "∩" },
      { command: "\\cup", symbol: "∪" },
      { command: "\\wedge", symbol: "∧" },
      { command: "\\vee", symbol: "∨" },
      { command: "\\sum", symbol: "∑" },
      { command: "\\prod", symbol: "∏" },
      { command: "\\int", symbol: "∫" },
      { command: "\\iint", symbol: "∬" },
      { command: "\\oint", symbol: "∮" },
    ],
  },
  {
    key: "relations",
    label: "关系符号",
    items: [
      { command: "=", symbol: "=" },
      { command: "\\neq", symbol: "≠" },
      { command: "\\equiv", symbol: "≡" },
      { command: "\\approx", symbol: "≈" },
      { command: "\\sim", symbol: "∼" },
      { command: "\\leq", symbol: "≤" },
      { command: "\\geq", symbol: "≥" },
      { command: "\\ll", symbol: "≪" },
      { command: "\\gg", symbol: "≫" },
      { command: "\\subset", symbol: "⊂" },
      { command: "\\supset", symbol: "⊃" },
      { command: "\\subseteq", symbol: "⊆" },
      { command: "\\supseteq", symbol: "⊇" },
      { command: "\\in", symbol: "∈" },
      { command: "\\notin", symbol: "∉" },
      { command: "\\perp", symbol: "⊥" },
      { command: "\\parallel", symbol: "∥" },
    ],
  },
  {
    key: "arrows",
    label: "箭头",
    items: [
      { command: "\\rightarrow", symbol: "→" },
      { command: "\\leftarrow", symbol: "←" },
      { command: "\\leftrightarrow", symbol: "↔" },
      { command: "\\Rightarrow", symbol: "⇒" },
      { command: "\\Leftarrow", symbol: "⇐" },
      { command: "\\Leftrightarrow", symbol: "⇔" },
      { command: "\\longrightarrow", symbol: "⟶" },
      { command: "\\mapsto", symbol: "↦" },
      { command: "\\uparrow", symbol: "↑" },
      { command: "\\downarrow", symbol: "↓" },
      { command: "\\rightleftharpoons", symbol: "⇌" },
    ],
  },
  {
    key: "matrix",
    label: "矩阵模板",
    items: [
      { command: "\\begin{pmatrix} a & b \\\\ c & d \\end{pmatrix}", symbol: "(2×2)" },
      { command: "\\begin{bmatrix} a & b \\\\ c & d \\end{bmatrix}", symbol: "[2×2]" },
      { command: "\\begin{cases} a & \\text{条件} \\\\ b & \\text{否则} \\end{cases}", symbol: "cases" },
      { command: "\\begin{vmatrix} a & b \\\\ c & d \\end{vmatrix}", symbol: "|2×2|" },
    ],
  },
  {
    key: "structures",
    label: "常用结构",
    items: [
      { command: "\\frac{分子}{分母}", symbol: "分数" },
      { command: "\\sqrt{被开方}", symbol: "根号" },
      { command: "\\sqrt[n]{被开方}", symbol: "n次根" },
      { command: "x^{上标}", symbol: "上标" },
      { command: "x_{下标}", symbol: "下标" },
      { command: "x_{i}^{2}", symbol: "上下标" },
      { command: "\\overline{AB}", symbol: "上划线" },
      { command: "\\hat{x}", symbol: "帽符" },
      { command: "\\widehat{AB}", symbol: "宽帽" },
      { command: "\\vec{v}", symbol: "向量" },
      { command: "\\binom{n}{k}", symbol: "二项式" },
      { command: "\\left( 表达式 \\right)", symbol: "自适应()" },
      { command: "\\text{文本}", symbol: "文本" },
      { command: "\\mathbf{x}", symbol: "粗体" },
      { command: "\\mathbb{R}", symbol: "数集" },
      { command: "\\mathcal{L}", symbol: "花体" },
      { command: "\\sum_{i=1}^{n}", symbol: "求和" },
      { command: "\\int_{a}^{b}", symbol: "积分限" },
      { command: "\\lim_{x \\to 0}", symbol: "极限" },
      { command: "\\infty", symbol: "∞" },
      { command: "\\partial", symbol: "∂" },
      { command: "\\nabla", symbol: "∇" },
      { command: "\\dots", symbol: "…" },
      { command: "\\,", symbol: "小间距" },
    ],
  },
];

export const FORMULA_TEMPLATES: CustomTemplate[] = [
  {
    name: "定积分",
    category: "微积分",
    code: "\\int_{a}^{b} f(x)\\,dx = F(b) - F(a)",
  },
  {
    name: "矩阵乘法",
    category: "线性代数",
    code:
      "\\begin{pmatrix} a & b \\\\ c & d \\end{pmatrix}" +
      "\\begin{pmatrix} x \\\\ y \\end{pmatrix}" +
      "= \\begin{pmatrix} ax+by \\\\ cx+dy \\end{pmatrix}",
  },
  {
    name: "正态分布",
    category: "概率统计",
    code:
      "f(x) = \\frac{1}{\\sigma\\sqrt{2\\pi}}" +
      "\\exp\\left(-\\frac{1}{2}" +
      "\\left(\\frac{x-\\mu}{\\sigma}\\right)^2\\right)",
  },
  {
    name: "方程组 (cases)",
    category: "常用结构",
    code:
      "f(x) = \\begin{cases} x^2 & \\text{if } x \\geq 0, " +
      "\\\\ -x & \\text{if } x < 0 \\end{cases}",
  },
  {
    name: "求和公式",
    category: "常用结构",
    code: "\\sum_{i=1}^{n} i^2 = \\frac{n(n+1)(2n+1)}{6}",
  },
  {
    name: "贝叶斯定理",
    category: "概率统计",
    code:
      "P(A\\mid B) = \\frac{P(B\\mid A)\\,P(A)}{P(B)}",
  },
  {
    name: "欧拉恒等式",
    category: "常用结构",
    code: "e^{i\\pi} + 1 = 0",
  },
  {
    name: "泰勒展开",
    category: "微积分",
    code:
      "f(x) = \\sum_{n=0}^{\\infty} \\frac{f^{(n)}(a)}{n!}(x-a)^n",
  },
  {
    name: "3×3 行列式",
    category: "线性代数",
    code:
      "\\begin{vmatrix} a & b & c \\\\ d & e & f \\\\ g & h & i \\end{vmatrix}",
  },
  {
    name: "带编号交叉引用",
    category: "交叉引用",
    code: "由 \\ref{label} 可知该结论成立",
  },
];
