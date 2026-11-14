"""Statistics helpers (exact, stdlib-only)."""
from __future__ import annotations

import math


def wilson(k: int, n: int, z: float = 1.959963984540054):
    """Wilson score interval for a binomial proportion."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((centre - margin) / denom, (centre + margin) / denom)


def clopper_pearson_upper_zero(n: int, alpha: float = 0.05) -> float:
    """Exact two-sided 95% CP upper bound when 0 failures observed."""
    if n <= 0:
        return 1.0
    return 1.0 - (alpha / 2.0) ** (1.0 / n)


def percentiles(values, ps=(50, 95, 99)):
    if not values:
        return {p: None for p in ps}
    xs = sorted(values)

    def pct(p):
        i = (len(xs) - 1) * p / 100.0
        lo = int(math.floor(i))
        hi = int(math.ceil(i))
        if lo == hi:
            return xs[lo]
        return xs[lo] + (xs[hi] - xs[lo]) * (i - lo)

    return {p: pct(p) for p in ps}


def rate(k: int, n: int) -> float | None:
    return k / n if n else None
