from __future__ import annotations
from datetime import date, timedelta
from typing import List, Set

def previous_complete_month(today: date) -> str:
  first_this = date(today.year, today.month, 1)
  last_prev = first_this - timedelta(days=1)
  return f"{last_prev.year:04d}-{last_prev.month:02d}"

def months_present(rows) -> List[str]:
  ms: Set[str] = set(r["month"] for r in rows)
  return sorted(ms)

def count_mondays_in_month(year: int, month: int, start_date: date | None = None) -> int:
  # Count Mondays in the month, filtered by start_date if provided
  d = date(year, month, 1)
  mondays = 0
  while d.month == month:
    if d.weekday() == 0:  # Monday
      if start_date is None or d >= start_date:
        mondays += 1
    d += timedelta(days=1)
  return mondays
