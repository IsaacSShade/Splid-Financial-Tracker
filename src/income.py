from __future__ import annotations
from datetime import datetime
from typing import Dict

from months import count_mondays_in_month

def month_to_ym(month_str: str) -> tuple[int,int]:
  y, m = month_str.split("-")
  return int(y), int(m)

def monthly_income(month: str, cfg_income) -> float:
  # 0 before startDate's month
  start = datetime.strptime(cfg_income.startDate, "%Y-%m-%d").date()
  y, m = month_to_ym(month)
  if (y, m) < (start.year, start.month):
    return 0.0

  # explicit override in hoursOverrides?
  if month in cfg_income.hoursOverrides:
    hours = float(cfg_income.hoursOverrides[month])
    return cfg_income.hourlyRate * hours

  # otherwise: defaultWeeklyHours * (# Mondays in month on/after startDate)
  mondays = count_mondays_in_month(y, m, start_date=start)
  hours = cfg_income.defaultWeeklyHours * mondays
  return cfg_income.hourlyRate * hours
