from __future__ import annotations
from typing import List, Dict
from datetime import datetime
from collections import defaultdict

from core.models import CreditCardTransaction

def _ym(d_iso: str) -> str:
    d = datetime.strptime(d_iso, "%Y-%m-%d").date()
    return f"{d.year:04d}-{d.month:02d}"

def calendarize(rows: List[CreditCardTransaction], use_post_date: bool = True) -> Dict[str, List[CreditCardTransaction]]:
    out: Dict[str, List[CreditCardTransaction]] = defaultdict(list)
    for r in rows:
        key = _ym(r.post_date if use_post_date else r.trans_date)
        out[key].append(r)
    return out
