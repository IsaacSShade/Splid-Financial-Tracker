from __future__ import annotations
from datetime import datetime
from typing import Dict

from core.dates import count_mondays_in_month

def month_to_ym(month_str: str) -> tuple[int,int]:
  y, m = month_str.split("-")
  return int(y), int(m)

def monthly_income(month: str, cfg_income) -> float:
  # 0 before startDate's month
  start = datetime.strptime(cfg_income.start_date, "%Y-%m-%d").date()
  y, m = month_to_ym(month)
  if (y, m) < (start.year, start.month):
    return 0.0

  # explicit override in hoursOverrides?
  if month in cfg_income.hours_overrides:
    hours = float(cfg_income.hours_overrides[month])
    return cfg_income.hourly_rate * hours

  # otherwise: defaultWeeklyHours * (# Mondays in month on/after startDate)
  mondays = count_mondays_in_month(y, m, start_date=start)
  hours = cfg_income.default_weekly_hours * mondays
  return cfg_income.hourly_rate * hours
