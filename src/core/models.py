from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from typing import List, Optional

MonthKey = str  # "YYYY-MM"

@dataclass
class WeekRange:
  week_start: date
  week_end: date

@dataclass
class WeeklyAllowance:
  week_start: date
  week_end: date
  allowance: float

@dataclass
class BudgetingCfg:
  week_start: str = "MON"              # "MON".."SUN"
  use_your_share: bool = True          # use your share vs total
  exclude_buckets: List[str] | None = None

  # forecasting controls
  window_months: int = 12              # recency lookback window
  min_months: int = 6                  # minimum months required to forecast
  seasonal_weight: float = 0.25        # weight on same-month-last-year anchor (if present)
  ewma_alpha: float = 0.5              # higher = favor recent months more
  outlier_method: str = "mad"          # "mad" | "winsor"
  outlier_k: float = 3.5               # aggressiveness for outlier detection
  
@dataclass
class CreditCardTransaction:
  trans_date: str     # YYYY-MM-DD
  post_date: str      # YYYY-MM-DD
  description: str
  amount: float       # +charges, -credits
  section: str        # "payments_credits" | "purchases_adjustments"
