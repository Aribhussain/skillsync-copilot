"""Krippendorff's alpha (in-house implementation; the PyPI `krippendorff` package is GPL).

Coincidence-matrix formulation (Krippendorff, "Computing Krippendorff's Alpha-Reliability"):
  units u, each with m_u >= 2 pairable values (missing values allowed)
  o_ck = sum_u (number of c-k pairs in u from different coders) / (m_u - 1)
  n_c  = sum_k o_ck,  n = sum_c n_c
  alpha = 1 - (n - 1) * sum_ck o_ck d2(c,k) / sum_ck n_c n_k d2(c,k)

Metrics d2(c, k):
  nominal   0 if c == k else 1
  interval  (c - k)^2
  ordinal   (sum_{g=c..k} n_g - (n_c + n_k) / 2)^2     (ranks c <= k)

Verified against the reference implementation on random and missing-data matrices
(see tests/test_krippendorff.py).
"""

from __future__ import annotations

from collections.abc import Sequence
from itertools import permutations

import numpy as np

Value = float | int | None


def _coincidences(data: Sequence[Sequence[Value]]) -> tuple[np.ndarray, list[float]]:
    """`data` is a units x coders matrix (None = missing)."""
    values = sorted({float(v) for unit in data for v in unit if v is not None})
    index = {v: i for i, v in enumerate(values)}
    o = np.zeros((len(values), len(values)))
    for unit in data:
        vals = [float(v) for v in unit if v is not None]
        m = len(vals)
        if m < 2:
            continue
        for a, b in permutations(range(m), 2):
            o[index[vals[a]], index[vals[b]]] += 1.0 / (m - 1)
    return o, values


def _delta2(values: list[float], n_c: np.ndarray, metric: str) -> np.ndarray:
    k = len(values)
    d = np.zeros((k, k))
    for i in range(k):
        for j in range(k):
            if metric == "nominal":
                d[i, j] = 0.0 if i == j else 1.0
            elif metric == "interval":
                d[i, j] = (values[i] - values[j]) ** 2
            elif metric == "ordinal":
                lo, hi = min(i, j), max(i, j)
                d[i, j] = (n_c[lo : hi + 1].sum() - (n_c[i] + n_c[j]) / 2.0) ** 2
            else:
                raise ValueError(f"Unknown metric {metric}")
    return d


def alpha(data: Sequence[Sequence[Value]], metric: str = "ordinal") -> float | None:
    """Krippendorff's alpha, or None when it is undefined (fewer than 2 pairable values or
    no variation at all in the data)."""
    o, values = _coincidences(data)
    if len(values) == 0:
        return None
    n_c = o.sum(axis=1)
    n = n_c.sum()
    if n <= 1:
        return None
    if len(values) == 1:
        return None  # perfect agreement on a single value: expected disagreement is 0
    d2 = _delta2(values, n_c, metric)
    observed = (o * d2).sum()
    expected = (np.outer(n_c, n_c) * d2).sum()
    if expected == 0:
        return None
    return float(1.0 - (n - 1) * observed / expected)
