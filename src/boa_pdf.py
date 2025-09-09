from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List, Iterable
import re
import pdfplumber
from dateutil import parser as dup

@dataclass
class CCRow:
    trans_date: str     # YYYY-MM-DD
    post_date: str      # YYYY-MM-DD
    description: str
    amount: float       # +charges, -credits
    section: str        # "payments_credits" | "purchases_adjustments"

_DATE = r"(?:\d{1,2}/\d{1,2})"
_AMT  = r"[-]?\$?\d{1,3}(?:,\d{3})*(?:\.\d{2})"
_LINE_RE = re.compile(rf"^\s*({_DATE})\s+({_DATE})\s+(.*\S)\s+({_AMT})\s*$")

def _to_iso(monthday: str, fallback_year: int) -> str:
    # monthday like "07/28" → use fallback_year to resolve
    dt = dup.parse(monthday + f"/{fallback_year}", dayfirst=False, yearfirst=False)
    return dt.date().isoformat()

def _to_amount(s: str) -> float:
    s2 = s.replace(",", "").replace("$", "").strip()
    return float(s2)

def _iter_text_lines(pdf_path: Path) -> Iterable[str]:
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                yield line.rstrip()

def parse_statement_pdf(pdf_path: Path) -> List[CCRow]:
    """
    Extracts transactions from a BoA statement PDF by scanning the 'Transactions' section.
    We detect two subsections: 'Payments and Other Credits' and 'Purchases and Adjustments'.
    """
    lines = list(_iter_text_lines(pdf_path))

    # detect statement year from header (e.g., 'Statement Closing Date 08/15/2025')
    year = None
    for ln in lines:
        if "Statement Closing Date" in ln:
            m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", ln)
            if m:
                year = int(m.group(3))
                break
    if year is None:
        # fallback: last 4-digit year on page
        m = re.search(r"(\d{4})", " ".join(lines))
        year = int(m.group(1)) if m else dup.parse("2000-01-01").year

    rows: List[CCRow] = []
    in_transactions = False
    in_section = None  # None | "payments_credits" | "purchases_adjustments"

    for ln in lines:
        low = ln.lower().strip()

        if not in_transactions and low.startswith("transactions"):
            in_transactions = True
            in_section = None
            continue

        if in_transactions:
            if low.startswith("payments and other credits"):
                in_section = "payments_credits"; continue
            if low.startswith("purchases and adjustments"):
                in_section = "purchases_adjustments"; continue
            if low.startswith("fees charged") or low.startswith("interest charged") or low.startswith("important information"):
                # end of transaction listing on many statements
                in_transactions = False
                in_section = None
                continue

            m = _LINE_RE.match(ln)
            if m and in_section:
                trans_m, post_m, desc, amt_s = m.groups()
                try:
                    tr = _to_iso(trans_m, year)
                    pr = _to_iso(post_m, year)
                    amt = _to_amount(amt_s)
                    # normalize sign: in BoA PDF amounts are already signed appropriately per section
                    rows.append(CCRow(tr, pr, desc.strip(), amt, in_section))
                except Exception:
                    # tolerate weird lines
                    pass

    return rows
