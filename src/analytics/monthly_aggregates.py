from __future__ import annotations
from typing import Dict, Iterable, Tuple, List

def monthly_living_totals(
    normalized_rows: Iterable[dict],
    use_your_share: bool = True,
    exclude_buckets: List[str] | None = None,
) -> Dict[str, float]:
    """Return { 'YYYY-MM': total } for living expenses only (exclude payments)."""
    ex = set(exclude_buckets or [])
    out: Dict[str, float] = {}
    for r in normalized_rows:
        if r.get("is_payment"):
            continue
        if r.get("bucket") in ex:
            continue
        amt = float(r["your_share"] if use_your_share else r["amount_total"])
        m = r["month"]
        out[m] = out.get(m, 0.0) + amt
    return out
