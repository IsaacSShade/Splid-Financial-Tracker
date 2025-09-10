from __future__ import annotations
from typing import List, Tuple
import math

def _median(xs: List[float]) -> float:
    s = sorted(xs)
    n = len(s)
    if n == 0: return 0.0
    mid = n // 2
    return (s[mid] if n % 2 == 1 else 0.5 * (s[mid - 1] + s[mid]))

def _mad(xs: List[float], med: float) -> float:
    dev = [abs(x - med) for x in xs]
    return _median(dev)

def remove_outliers_mad(xs: List[float], k: float) -> List[float]:
    """Return xs with points removed where |x-med|/MAD > k (robust)."""
    if not xs: return xs
    med = _median(xs)
    mad = _mad(xs, med) or 1e-9  # avoid div by zero
    keep = []
    for x in xs:
        if abs(x - med) / mad <= k:
            keep.append(x)
    return keep

def winsorize(xs: List[float], k: float) -> List[float]:
    """Clamp tails using MAD threshold; keep length same."""
    if not xs: return xs
    med = _median(xs)
    mad = _mad(xs, med) or 1e-9
    lo = med - k * mad
    hi = med + k * mad
    return [min(max(x, lo), hi) for x in xs]
