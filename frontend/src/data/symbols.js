// 符号面板数据：按分类罗列常见数学符号，点击即在光标处插入。
// code 为插入的 LaTeX；display 为面板上展示的纯文本（若与 code 相同可省略）。
export const SYMBOL_CATEGORIES = [
  {
    key: "greek",
    label: "希腊字母",
    symbols: [
      { code: "\\alpha" }, { code: "\\beta" }, { code: "\\gamma" },
      { code: "\\delta" }, { code: "\\epsilon" }, { code: "\\varepsilon" },
      { code: "\\zeta" }, { code: "\\eta" }, { code: "\\theta" },
      { code: "\\vartheta" }, { code: "\\iota" }, { code: "\\kappa" },
      { code: "\\lambda" }, { code: "\\mu" }, { code: "\\nu" },
      { code: "\\xi" }, { code: "\\pi" }, { code: "\\varpi" },
      { code: "\\rho" }, { code: "\\varrho" }, { code: "\\sigma" },
      { code: "\\tau" }, { code: "\\upsilon" }, { code: "\\phi" },
      { code: "\\varphi" }, { code: "\\chi" }, { code: "\\psi" },
      { code: "\\omega" },
      { code: "\\Gamma" }, { code: "\\Delta" }, { code: "\\Theta" },
      { code: "\\Lambda" }, { code: "\\Xi" }, { code: "\\Pi" },
      { code: "\\Sigma" }, { code: "\\Upsilon" }, { code: "\\Phi" },
      { code: "\\Psi" }, { code: "\\Omega" },
    ],
  },
  {
    key: "operators",
    label: "运算符",
    symbols: [
      { code: "+" }, { code: "-" }, { code: "\\pm" }, { code: "\\mp" },
      { code: "\\times" }, { code: "\\div" }, { code: "\\cdot" },
      { code: "\\ast" }, { code: "\\star" }, { code: "\\circ" },
      { code: "\\bullet" }, { code: "\\oplus" }, { code: "\\ominus" },
      { code: "\\otimes" }, { code: "\\oslash" }, { code: "\\odot" },
      { code: "\\sum" }, { code: "\\prod" }, { code: "\\coprod" },
      { code: "\\int" }, { code: "\\oint" }, { code: "\\iint" },
      { code: "\\iiint" }, { code: "\\bigcup" }, { code: "\\bigcap" },
      { code: "\\bigvee" }, { code: "\\bigwedge" }, { code: "\\setminus" },
      { code: "\\sqrt{}" }, { code: "\\frac{}{}" }, { code: "\\binom{}{}" },
    ],
  },
  {
    key: "relations",
    label: "关系符号",
    symbols: [
      { code: "=" }, { code: "\\neq" }, { code: "\\leq" }, { code: "\\geq" },
      { code: "\\ll" }, { code: "\\gg" }, { code: "\\approx" },
      { code: "\\equiv" }, { code: "\\sim" }, { code: "\\simeq" },
      { code: "\\cong" }, { code: "\\propto" }, { code: "\\doteq" },
      { code: "<" }, { code: ">" }, { code: "\\subset" },
      { code: "\\supset" }, { code: "\\subseteq" }, { code: "\\supseteq" },
      { code: "\\in" }, { code: "\\notin" }, { code: "\\ni" },
      { code: "\\perp" }, { code: "\\parallel" }, { code: "\\mid" },
      { code: ":" },
    ],
  },
  {
    key: "arrows",
    label: "箭头",
    symbols: [
      { code: "\\leftarrow" }, { code: "\\rightarrow" },
      { code: "\\leftrightarrow" }, { code: "\\Leftarrow" },
      { code: "\\Rightarrow" }, { code: "\\Leftrightarrow" },
      { code: "\\longleftarrow" }, { code: "\\longrightarrow" },
      { code: "\\mapsto" }, { code: "\\longmapsto" },
      { code: "\\uparrow" }, { code: "\\downarrow" },
      { code: "\\updownarrow" }, { code: "\\Uparrow" },
      { code: "\\Downarrow" }, { code: "\\nearrow" },
      { code: "\\searrow" }, { code: "\\swarrow" }, { code: "\\nwarrow" },
      { code: "\\rightharpoonup" }, { code: "\\rightharpoondown" },
    ],
  },
  {
    key: "structures",
    label: "常用结构",
    symbols: [
      { code: "^{}" }, { code: "_{}" }, { code: "_{}^{}" },
      { code: "\\hat{}" }, { code: "\\bar{}" }, { code: "\\vec{}" },
      { code: "\\dot{}" }, { code: "\\ddot{}" }, { code: "\\tilde{}" },
      { code: "\\widehat{}" }, { code: "\\widetilde{}" },
      { code: "\\overline{}" }, { code: "\\underline{}" },
      { code: "\\overbrace{}" }, { code: "\\underbrace{}" },
      { code: "\\boxed{}" }, { code: "\\text{}" },
      { code: "\\mathrm{}" }, { code: "\\mathbf{}" }, { code: "\\mathbb{}" },
      { code: "\\mathcal{}" }, { code: "\\left(\\right)" },
      { code: "\\left[\\right]" }, { code: "\\left\\{\\right\\}" },
      { code: "\\left|\\right|" }, { code: "\\langle\\rangle" },
      { code: "\\lfloor\\rfloor" }, { code: "\\lceil\\rceil" },
      { code: "\\infty" }, { code: "\\partial" }, { code: "\\nabla" },
      { code: "\\forall" }, { code: "\\exists" }, { code: "\\varnothing" },
      { code: "\\quad" }, { code: "\\qquad" }, { code: "\\cdots" },
      { code: "\\ldots" }, { code: "\\vdots" }, { code: "\\ddots" },
      { code: "\\dots" }, { code: "\\degree" },
    ],
  },
];

// 矩阵/对齐模板单独由 MatrixPanel 负责（属于“矩阵模板”分类）
export const MATRIX_INSERTS = [
  {
    label: "2×2 矩阵 ( )",
    code: "\\begin{pmatrix} a & b \\\\ c & d \\end{pmatrix}",
  },
  {
    label: "2×2 矩阵 [ ]",
    code: "\\begin{bmatrix} a & b \\\\ c & d \\end{bmatrix}",
  },
  {
    label: "行列式 | |",
    code: "\\begin{vmatrix} a & b \\\\ c & d \\end{vmatrix}",
  },
  {
    label: "3×3 矩阵",
    code:
      "\\begin{pmatrix} a & b & c \\\\ d & e & f \\\\ g & h & i " +
      "\\end{pmatrix}",
  },
  {
    label: "行内对齐",
    code: "\\begin{aligned} x &= 1 \\\\ y &= 2 \\end{aligned}",
  },
];

// 公式模板库：点击插入完整骨架，再改参数。
export const FORMULA_TEMPLATES = [
  {
    key: "definite-integral",
    name: "定积分",
    code: "\\int_{a}^{b} f(x)\\,\\mathrm{d}x",
  },
  {
    key: "double-integral",
    name: "二重积分",
    code: "\\iint_{D} f(x,y)\\,\\mathrm{d}x\\,\\mathrm{d}y",
  },
  {
    key: "matrix-product",
    name: "矩阵乘法",
    code:
      "\\begin{pmatrix} a & b \\\\ c & d \\end{pmatrix}" +
      "\\begin{pmatrix} x \\\\ y \\end{pmatrix}" +
      "= \\begin{pmatrix} ax+by \\\\ cx+dy \\end{pmatrix}",
  },
  {
    key: "normal-distribution",
    name: "正态分布",
    code:
      "f(x) = \\frac{1}{\\sqrt{2\\pi\\sigma^{2}}}" +
      "\\exp\\left(-\\frac{(x-\\mu)^{2}}{2\\sigma^{2}}\\right)",
  },
  {
    key: "equation-system",
    name: "方程组 (cases)",
    code:
      "\\begin{cases} x + y = 1 \\\\ 2x - y = 0 \\end{cases}",
  },
  {
    key: "quadratic",
    name: "二次方程求根",
    code: "x = \\frac{-b \\pm \\sqrt{b^{2} - 4ac}}{2a}",
  },
  {
    key: "sum-series",
    name: "级数求和",
    code: "\\sum_{n=1}^{\\infty} \\frac{1}{n^{2}} = \\frac{\\pi^{2}}{6}",
  },
  {
    key: "limit",
    name: "极限",
    code:
      "\\lim_{x \\to 0} \\frac{\\sin x}{x} = 1",
  },
  {
    key: "partial-derivative",
    name: "偏导数",
    code:
      "\\frac{\\partial f}{\\partial x}(x_0,y_0)",
  },
  {
    key: "bayes",
    name: "贝叶斯公式",
    code:
      "P(A\\mid B) = \\frac{P(B\\mid A)\\,P(A)}{P(B)}",
  },
  {
    key: "cross-reference",
    name: "引用其它公式",
    code: "由式 \\eqref{eq:label} 可得",
  },
];
