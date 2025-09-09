from __future__ import annotations
from typing import List, Dict
from datetime import datetime
from collections import defaultdict
from boa_pdf import CCRow

def _ym(d_iso: str) -> str:
    d = datetime.strptime(d_iso, "%Y-%m-%d").date()
    return f"{d.year:04d}-{d.month:02d}"

def calendarize(rows: List[CCRow], use_post_date: bool = True) -> Dict[str, List[CCRow]]:
    out: Dict[str, List[CCRow]] = defaultdict(list)
    for r in rows:
        key = _ym(r.post_date if use_post_date else r.trans_date)
        out[key].append(r)
    return out
