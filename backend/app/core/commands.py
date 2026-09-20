"""LaTeX command catalogue.

This module is the single source of truth about *which* LaTeX control
sequences the backend understands.  It is shared by:

* the lexer / structural parser (argument arity per command),
* the MathML renderer (glyphs and structures),
* the spelling suggester (the set of "known" commands),
* the symbol panel on the frontend (a serialized view is exposed over HTTP).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Greek letters
# ---------------------------------------------------------------------------

GREEK: dict[str, str] = {
    r"\alpha": "α", r"\beta": "β", r"\gamma": "γ", r"\delta": "δ",
    r"\epsilon": "ϵ", r"\varepsilon": "ε", r"\zeta": "ζ", r"\eta": "η",
    r"\theta": "θ", r"\vartheta": "ϑ", r"\iota": "ι", r"\kappa": "κ",
    r"\lambda": "λ", r"\mu": "μ", r"\nu": "ν", r"\xi": "ξ",
    r"\pi": "π", r"\varpi": "ϖ", r"\rho": "ρ", r"\varrho": "ϱ",
    r"\sigma": "σ", r"\varsigma": "ς", r"\tau": "τ", r"\upsilon": "υ",
    r"\phi": "ϕ", r"\varphi": "φ", r"\chi": "χ", r"\psi": "ψ",
    r"\omega": "ω",
    r"\Gamma": "Γ", r"\Delta": "Δ", r"\Theta": "Θ", r"\Lambda": "Λ",
    r"\Xi": "Ξ", r"\Pi": "Π", r"\Sigma": "Σ", r"\Upsilon": "Υ",
    r"\Phi": "Φ", r"\Psi": "Ψ", r"\Omega": "Ω",
}

# ---------------------------------------------------------------------------
# Binary / large operators
# ---------------------------------------------------------------------------

BINARY_OPERATORS: dict[str, str] = {
    r"\pm": "±", r"\mp": "∓", r"\times": "×", r"\div": "÷",
    r"\cdot": "⋅", r"\ast": "∗", r"\star": "⋆", r"\circ": "∘",
    r"\bullet": "•", r"\cap": "∩", r"\cup": "∪", r"\wedge": "∧",
    r"\vee": "∨", r"\setminus": "∖", r"\oplus": "⊕", r"\ominus": "⊖",
    r"\otimes": "⊗", r"\oslash": "⊘", r"\odot": "⊙", r"\dagger": "†",
    r"\ddagger": "‡", r"\amalg": "⨿",
}

# Big operators take (optionally) limits and move their limits in display
# style (movablelimits).
BIG_OPERATORS: dict[str, str] = {
    r"\sum": "∑", r"\prod": "∏", r"\coprod": "∐", r"\int": "∫",
    r"\iint": "∬", r"\iiint": "∭", r"\oint": "∮", r"\bigcup": "⋃",
    r"\bigcap": "⋂", r"\bigvee": "⋁", r"\bigwedge": "⋀",
    r"\bigoplus": "⨁", r"\bigotimes": "⨂",
}

# ---------------------------------------------------------------------------
# Relations
# ---------------------------------------------------------------------------

RELATIONS: dict[str, str] = {
    r"=": "=", r"\neq": "≠", r"\ne": "≠", r"\equiv": "≡",
    r"\approx": "≈", r"\sim": "∼", r"\simeq": "≃", r"\cong": "≅",
    r"\propto": "∝", r"\doteq": "≐",
    r"<": "<", r">": ">", r"\le": "≤", r"\leq": "≤", r"\ge": "≥",
    r"\geq": "≥", r"\ll": "≪", r"\gg": "≫", r"\prec": "≺",
    r"\succ": "≻", r"\preceq": "≼", r"\succeq": "≽", r"\subset": "⊂",
    r"\supset": "⊃", r"\subseteq": "⊆", r"\supseteq": "⊇",
    r"\sqsubset": "⊏", r"\sqsupset": "⊐", r"\sqsubseteq": "⊑",
    r"\sqsupseteq": "⊒", r"\in": "∈", r"\ni": "∋", r"\notin": "∉",
    r"\perp": "⊥", r"\parallel": "∥", r"\mid": "∣", r"\vdash": "⊢",
    r"\dashv": "⊣", r"\models": "⊨",
}

# ---------------------------------------------------------------------------
# Arrows
# ---------------------------------------------------------------------------

ARROWS: dict[str, str] = {
    r"\rightarrow": "→", r"\to": "→", r"\leftarrow": "←",
    r"\leftrightarrow": "↔", r"\Rightarrow": "⇒", r"\Leftarrow": "⇐",
    r"\Leftrightarrow": "⇔", r"\longrightarrow": "⟶",
    r"\longleftarrow": "⟵", r"\mapsto": "↦", r"\longmapsto": "⟼",
    r"\uparrow": "↑", r"\downarrow": "↓", r"\Uparrow": "⇑",
    r"\Downarrow": "⇓", r"\nearrow": "↗", r"\searrow": "↘",
    r"\swarrow": "↙", r"\nwarrow": "↖", r"\rightharpoonup": "⇀",
    r"\rightharpoondown": "⇁", r"\leftharpoonup": "↼",
    r"\leftharpoondown": "↽", r"\rightleftharpoons": "⇌",
}

# ---------------------------------------------------------------------------
# Dots, misc symbols, delimiters
# ---------------------------------------------------------------------------

DOTS: dict[str, str] = {
    r"\dots": "…", r"\ldots": "…", r"\cdots": "⋯", r"\vdots": "⋮",
    r"\ddots": "⋱",
}

MISC_SYMBOLS: dict[str, str] = {
    r"\infty": "∞", r"\partial": "∂", r"\nabla": "∇", r"\forall": "∀",
    r"\exists": "∃", r"\nexists": "∄", r"\emptyset": "∅",
    r"\varnothing": "∅", r"\neg": "¬", r"\lnot": "¬", r"\therefore": "∴",
    r"\because": "∵", r"\Re": "ℜ", r"\Im": "ℑ", r"\aleph": "ℵ",
    r"\hbar": "ℏ", r"\ell": "ℓ", r"\wp": "℘", r"\angle": "∠",
    r"\triangle": "△", r"\square": "□", r"\clubsuit": "♣",
    r"\diamondsuit": "♢", r"\heartsuit": "♡", r"\spadesuit": "♠",
    r"\prime": "′", r"\top": "⊤", r"\bot": "⊥", r"\checkmark": "✓",
}

DELIMITERS: dict[str, str] = {
    r"\{": "{", r"\}": "}", r"\lbrace": "{", r"\rbrace": "}",
    r"\langle": "⟨", r"\rangle": "⟩", r"\lfloor": "⌊", r"\rfloor": "⌋",
    r"\lceil": "⌈", r"\rceil": "⌉", r"\lbrack": "[", r"\rbrack": "]",
    r"\|": "‖",
}

# Spacing: rendered as <mspace width=.../>
SPACING: dict[str, str] = {
    r"\,": "0.1667em", r"\:": "0.2222em", r"\;": "0.2778em",
    r"\!": "-0.1667em", r"~": "0.25em",
}

# Commands that are structural or otherwise rendered specially.
STRUCTURAL = {
    r"\frac", r"\dfrac", r"\tfrac",  # 2 mandatory groups
    r"\binom", r"\tbinom", r"\dbinom",
    r"\sqrt",                         # 1 mandatory group + optional degree
    r"\overline", r"\underline", r"\overrightarrow", r"\overleftarrow",
    r"\hat", r"\bar", r"\vec", r"\dot", r"\ddot", r"\tilde", r"\widehat",
    r"\widetilde", r"\overline", r"\mathring",
    r"\text", r"\mathrm", r"\mathbf", r"\mathit", r"\mathcal",
    r"\mathbb", r"\mathfrak", r"\mathsf", r"\mathtt", r"\boldsymbol",
    r"\operatorname",
    r"\begin", r"\end", r"\left", r"\right",
    r"\limits", r"\nolimits", r"\displaystyle", r"\textstyle",
    r"\scriptstyle", r"\scriptscriptstyle", r"\\", r"\,", r"\:", r"\;",
    r"\!", r"\quad", r"\qquad", r"\,", r"\ref", r"\label",
}

# Standard named functions: <mo class="MathClass-op"> so MathML applies the
# proper spacing; they take no arguments.
FUNCTIONS = {
    r"\sin", r"\cos", r"\tan", r"\cot", r"\sec", r"\csc",
    r"\sinh", r"\cosh", r"\tanh", r"\coth",
    r"\arcsin", r"\arccos", r"\arctan",
    r"\exp", r"\log", r"\ln", r"\lg",
    r"\lim", r"\limsup", r"\liminf", r"\sup", r"\inf", r"\min", r"\max",
    r"\det", r"\dim", r"\gcd", r"\deg", r"\arg", r"\hom", r"\ker",
    r"\Pr",
}

# Matrix / tabular-like environments.
MATRIX_ENVS = {
    "matrix", "pmatrix", "bmatrix", "Bmatrix", "vmatrix", "Vmatrix",
}
ALIGN_ENVS = {"aligned", "cases", "split"}
KNOWN_ENVS = MATRIX_ENVS | ALIGN_ENVS | {"array"}

# Matrix environment -> (left fence, right fence)
MATRIX_FENCES: dict[str, tuple[str, str]] = {
    "matrix": ("", ""),
    "pmatrix": ("(", ")"),
    "bmatrix": ("[", "]"),
    "Bmatrix": ("{", "}"),
    "vmatrix": ("|", "|"),
    "Vmatrix": ("‖", "‖"),
}

# ---------------------------------------------------------------------------
# Aggregates
# ---------------------------------------------------------------------------

GLYPH_COMMANDS: dict[str, str] = {}
for _table in (
    GREEK, BINARY_OPERATORS, BIG_OPERATORS, RELATIONS, ARROWS, DOTS,
    MISC_SYMBOLS, DELIMITERS,
):
    GLYPH_COMMANDS.update(_table)

# Font modifier commands -> mathvariant attribute
FONT_VARIANTS: dict[str, str] = {
    r"\mathrm": "normal",
    r"\mathbf": "bold",
    r"\mathit": "italic",
    r"\mathsf": "sans-serif",
    r"\mathtt": "monospace",
    r"\mathcal": "script",
    r"\mathbb": "double-struck",
    r"\mathfrak": "fraktur",
}

ACCENTS: dict[str, str] = {
    r"\hat": "&#x0005E;",
    r"\bar": "_",
    r"\vec": "→",
    r"\dot": ".",
    r"\ddot": "..",
    r"\tilde": "~",
    r"\widehat": "&#x0005E;",
    r"\widetilde": "~",
    r"\mathring": "&#x000B0;",
}

OVERS = {
    r"\overrightarrow": ("→", "under"),
    r"\overleftarrow": ("←", "under"),
}

# Groups consumed by the parser as mandatory arguments, by command.
ARITY: dict[str, int] = {}
for _cmd in (r"\frac", r"\dfrac", r"\tfrac", r"\binom", r"\dbinom",
             r"\tbinom"):
    ARITY[_cmd] = 2
for _cmd in (
    r"\sqrt", r"\overline", r"\underline", r"\text", r"\operatorname",
    r"\boldsymbol",
):
    ARITY[_cmd] = 1
for _cmd in FONT_VARIANTS:
    ARITY.setdefault(_cmd, 1)
for _cmd in ACCENTS:
    ARITY.setdefault(_cmd, 1)
for _cmd in OVERS:
    ARITY.setdefault(_cmd, 1)
ARITY[r"\ref"] = 1
ARITY[r"\label"] = 1


def all_known_commands() -> set[str]:
    """Return the full set of recognized control sequences."""
    known = set(GLYPH_COMMANDS) | STRUCTURAL | FUNCTIONS
    known.update(ARITY)
    known.discard(r"\,")
    known.add(r"\,")
    return known
