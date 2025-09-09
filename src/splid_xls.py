from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd

_REQ = {"title", "amount", "by", "category"}  # plus date/created on

def _to_str(x) -> str:
    if pd.isna(x):
        return ""
    return str(x)

def _to_num(x) -> float:
    if pd.isna(x) or x == "":
        return 0.0
    s = str(x)
    neg = "(" in s and ")" in s
    s2 = s.replace("$", "").replace(",", "").replace("(", "").replace(")", "").strip()
    try:
        v = float(s2)
    except Exception:
        v = 0.0
    return -abs(v) if neg else v

def _find_header_idx(df_raw: pd.DataFrame) -> int:
    scan = min(10, len(df_raw))
    best_i, best_nonempty = 0, -1
    for i in range(scan):
        row = df_raw.iloc[i].map(_to_str).str.strip().str.lower().tolist()
        cols = {c for c in row if c}
        has_req = _REQ.issubset(cols) and ("created on" in cols or "date" in cols)
        if has_req:
            return i
        nonempty = len(cols)
        if nonempty > best_nonempty:
            best_i, best_nonempty = i, nonempty
    return best_i  # fallback: “most filled” among first rows

def _find_col(df: pd.DataFrame, names: list[str]) -> str | None:
    low = {c.strip().lower(): c for c in df.columns if isinstance(c, str)}
    for n in names:
        if n in low:
            return low[n]
    return None

def _find_name_col(df: pd.DataFrame, your_name: str) -> int:
    cols = list(df.columns)
    # exact first, then case-insensitive
    try:
        return cols.index(your_name)
    except ValueError:
        for i, c in enumerate(cols):
            if isinstance(c, str) and c.strip().lower() == your_name.strip().lower():
                return i
    raise ValueError(f"Could not find your name '{your_name}' in the header row.")

def parse_splid_xls(xls_path: Path, your_name: str) -> List[Dict[str, Any]]:
    # pass 1: sniff header row
    df_raw = pd.read_excel(xls_path, header=None, dtype=object, engine="xlrd")
    header_idx = _find_header_idx(df_raw)

    # pass 2: proper headered frame
    df = pd.read_excel(xls_path, header=header_idx, dtype=object, engine="xlrd")

    title_col    = _find_col(df, ["title"])
    amount_col   = _find_col(df, ["amount", "total", "value"])
    currency_col = _find_col(df, ["currency"])
    by_col       = _find_col(df, ["by", "paid by", "payer"])
    date_col     = _find_col(df, ["created on", "date"])
    category_col = _find_col(df, ["category"])

    if not title_col or not amount_col or not by_col or not date_col or not category_col:
        raise ValueError(f"Missing expected columns. Found: {list(df.columns)}")

    name_idx = _find_name_col(df, your_name)
    share_idx = name_idx + 1  # Splid puts your per-item share in the column right after your name
    
    # If the immediate next column has almost all zeros, scan the next 3 columns for a better candidate.
    def _col_signal(idx: int) -> int:
        if idx >= df.shape[1]: return -1
        col = df.iloc[:, idx]
        # signal = how many non-zero numeric-ish values are present
        def nz(x): 
            try:
                return abs(_to_num(x)) > 0.0001
            except Exception:
                return False
        return int(col.map(nz).sum())

    signal = _col_signal(share_idx)
    if signal < max(3, int(0.03 * len(df))):
        best_idx, best_sig = share_idx, signal
        for j in range(share_idx+1, min(share_idx+4, df.shape[1])):
            sig = _col_signal(j)
            if sig > best_sig:
                best_idx, best_sig = j, sig
        share_idx = best_idx

    out: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        title = _to_str(row.get(title_col)).strip()
        amount_total = _to_num(row.get(amount_col))
        currency = _to_str(row.get(currency_col)).strip() or "USD"
        by = _to_str(row.get(by_col)).strip()
        date_val = row.get(date_col)
        # Keep the raw; normalization handles parsing
        date_raw = _to_str(date_val).strip()
        category = _to_str(row.get(category_col)).strip()

        # share by positional index to catch "Unnamed: NN" cases
        try:
            your_share_raw = row.iat[share_idx]
        except Exception:
            your_share_raw = ""
        your_share = abs(_to_num(your_share_raw))

        # skip truly empty rows
        if not any([title, amount_total, your_share]):
            continue

        out.append({
            "title": title,
            "amount_total": amount_total,
            "currency": currency,
            "by": by,
            "date_raw": date_raw,
            "category_raw": category,
            "your_share": your_share
        })
    return out
