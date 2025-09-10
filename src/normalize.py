from __future__ import annotations
import re
from datetime import datetime
from dateutil import parser as dup
from typing import Dict, Any, List

def parse_date_or_none(s: str):
  if not s: return None
  # Try robust parse; fall back to None
  try:
    return dup.parse(s).date()
  except Exception:
    try:
      return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
      return None

def month_key(d) -> str:
  return f"{d.year:04d}-{d.month:02d}"

def build_bucket_resolvers(bucket_cfg) -> tuple:
  # Precompile regex rules for titleToBucket
  rules = []
  for patt, bucket in bucket_cfg.title_to_bucket.items():
    rules.append( (re.compile(patt, re.IGNORECASE), bucket) )
  cat_map = bucket_cfg.category_to_bucket
  payment_titles = [t.lower() for t in bucket_cfg.payment_title_exact]
  return rules, cat_map, payment_titles

def apply_bucket(title: str, category_raw: str, rules, cat_map) -> str:
  # Start from exact Category mapping
  bucket = cat_map.get(category_raw, category_raw.strip().lower() or "uncategorized")
  # Refine by title regex if matched (lets us split House bills into rent|utilities)
  for rx, b in rules:
    if rx.search(title or ""):
      bucket = b
      break
  return bucket

def normalize_rows(raw_rows: List[Dict[str,Any]], bucket_cfg) -> List[Dict[str,Any]]:
  rules, cat_map, payment_titles = build_bucket_resolvers(bucket_cfg)

  out = []
  for r in raw_rows:
    d = parse_date_or_none(r.get("date_raw",""))
    if d is None:
      # skip rows without usable dates
      continue
    t = (r.get("title") or "").strip()
    is_payment = t.lower() in payment_titles

    bucket = apply_bucket(t, r.get("category_raw",""), rules, cat_map)

    out.append({
      "date": d.isoformat(),
      "month": month_key(d),
      "title": t,
      "payer": r.get("by",""),
      "category_raw": r.get("category_raw",""),
      "bucket": bucket,
      "amount_total": float(r.get("amount_total",0.0)),
      "your_share": float(r.get("your_share",0.0)),
      "is_payment": bool(is_payment)
    })
  return out
