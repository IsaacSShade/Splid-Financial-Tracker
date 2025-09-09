from __future__ import annotations
from typing import List, Tuple, Dict
from datetime import datetime
from boa_pdf import CCRow

def _to_date(s: str):
    return datetime.strptime(s, "%Y-%m-%d").date()

def _diff_days(a: str, b: str) -> int:
    return abs((_to_date(a) - _to_date(b)).days)

def exact_match(
    cc_rows_m: List[CCRow],
    splid_rows_m: List[dict],
    your_name: str,
    amount_tol_cents: int = 0,
    date_window_days: int = 0,
    only_if_payer_is_you: bool = True
) -> Tuple[List[CCRow], List[CCRow]]:
    """
    Returns (matched_house_on_card, unmatched_fun).
    Match rule: |amount_cc - amount_splid_total| <= tol, |post_date - splid_date| <= window, payer matches if required.
    """
    # pre-index Splid by amount (full amount_total), within tolerance
    by_amount: Dict[int, List[dict]] = {}
    for r in splid_rows_m:
        if r["is_payment"]:
            continue
        if only_if_payer_is_you and (r.get("payer","").strip().lower() != your_name.strip().lower()):
            continue
        cents = int(round(float(r["amount_total"]) * 100))
        by_amount.setdefault(cents, []).append(r)

    matched: List[CCRow] = []
    unmatched: List[CCRow] = []

    for c in cc_rows_m:
        if c.section != "purchases_adjustments":
            # ignore payments & credits for spend
            continue
        cents_c = int(round(c.amount * 100))
        candidates = []
        for delta in range(-amount_tol_cents, amount_tol_cents + 1):
            candidates += by_amount.get(cents_c + delta, [])
        hit = None
        for s in candidates:
            if _diff_days(c.post_date, s["date"]) <= date_window_days:
                hit = s
                break
        if hit:
            matched.append(c)
        else:
            unmatched.append(c)

    return matched, unmatched
