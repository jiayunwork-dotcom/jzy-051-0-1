"""Spelling suggestions for unknown LaTeX commands and environments.

Contract
--------
``suggest_command(raw_command, limit=1)`` returns the closest known control
sequence(s) to *raw_command*, or ``None`` when nothing is close enough to be
trustworthy.  Input may include or omit the leading backslash.

``suggest_env(env_name)`` does the same for environment names
(``matrix``, ``pmatrix`` ...).

The metric is Damerau–Levenshtein distance (insertions, deletions,
substitutions and transpositions of two adjacent characters — ``\alhpa`` vs
``\alpha`` is the canonical LaTeX typo) with small domain tweaks:

* dropping the leading backslash costs 0 when both sides have/lack one;
* suggestions whose relative distance exceeds ``MAX_RATIO`` are rejected so
  that arbitrary garbage never yields a confident-looking "did you mean".

Ties are broken by (shorter name, then lexicographic) so the result is
deterministic for automated tests.
"""

from __future__ import annotations

from . import commands as cmd

MAX_RATIO = 0.34          # max distance / max(len) for a suggestion
MIN_LEN_FOR_SUGGEST = 2   # 1-char typos like "\z" get no suggestion


def _strip_backslash(name: str) -> str:
    return name[1:] if name.startswith("\\") else name


def damerau_levenshtein(a: str, b: str) -> int:
    """Classic DL distance with adjacent-transposition support."""
    n, m = len(a), len(b)
    if n == 0:
        return m
    if m == 0:
        return n
    # d[i][j] = distance between a[:i] and b[:j]
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(
                d[i - 1][j] + 1,       # deletion
                d[i][j - 1] + 1,       # insertion
                d[i - 1][j - 1] + cost,  # substitution
            )
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] \
                    and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)  # transposition
    return d[n][m]


def _rank(word: str, candidates) -> list[str]:
    scored: list[tuple[int, str]] = []
    for cand in candidates:
        dist = damerau_levenshtein(word, cand)
        ratio = dist / max(len(word), len(cand))
        if ratio <= MAX_RATIO:
            scored.append((dist, cand))
    scored.sort(key=lambda pair: (pair[0], len(pair[1]), pair[1]))
    return [cand for _, cand in scored]


def suggest_command(raw_command: str, limit: int = 1) -> str | list[str] | None:
    word = _strip_backslash(raw_command)
    if len(word) < MIN_LEN_FOR_SUGGEST:
        return None
    candidates = sorted({_strip_backslash(c)
                         for c in cmd.all_known_commands()})
    ranked = _rank(word, candidates)
    if not ranked:
        return None
    ranked = ["\\" + c for c in ranked[: max(limit, 1)]]
    return ranked[0] if limit == 1 else ranked


def suggest_env(env_name: str, limit: int = 1) -> str | list[str] | None:
    word = _strip_backslash(env_name)
    if len(word) < MIN_LEN_FOR_SUGGEST:
        return None
    ranked = _rank(word, sorted(cmd.KNOWN_ENVS))
    if not ranked:
        return None
    ranked = ranked[: max(limit, 1)]
    return ranked[0] if limit == 1 else ranked
