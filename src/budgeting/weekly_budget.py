from __future__ import annotations
from datetime import date, timedelta
from typing import List, Dict, Tuple

from core.models import BudgetingCfg, WeekRange, WeeklyAllowance, MonthKey
from analytics.monthly_aggregates import monthly_living_totals
from analytics.outliers import remove_outliers_mad, winsorize

_DAY_OF_WEEK = {"MON":0, "TUE":1, "WED":2, "THU":3, "FRI":4, "SAT":5, "SUN":6}

def compute_weeks_in_month(month: MonthKey, start_weekday: str = "MON") -> List[WeekRange]:
    y, m = map(int, month.split("-"))
    start = date(y, m, 1)
    # find month end
    d = start
    while True:
        try:
            _ = date(y, m, d.day + 1)
            d = _
        except ValueError:
            month_end = d
            break
    # align to first start_weekday on/after the 1st
    dow = _DAY_OF_WEEK.get(start_weekday.upper(), 0)
    d = start
    while d.weekday() != dow:
        d += timedelta(days=1)

    weeks: List[WeekRange] = []
    while d <= month_end:
        w_end = min(d + timedelta(days=6), month_end)
        weeks.append(WeekRange(week_start=d, week_end=w_end))
        d = w_end + timedelta(days=1)
        while d.weekday() != dow and d <= month_end:
            d += timedelta(days=1)
    return weeks

def _ym_to_prev_year_same_month(month: MonthKey) -> MonthKey:
    y, m = map(int, month.split("-"))
    return f"{y-1:04d}-{m:02d}"

def _sort_month_keys(keys: List[MonthKey]) -> List[MonthKey]:
    return sorted(keys)

def _ewma(values_in_time_order: List[float], alpha: float) -> float:
    # newest is last
    if not values_in_time_order:
        return 0.0
    s = values_in_time_order[0]
    for v in values_in_time_order[1:]:
        s = alpha * v + (1 - alpha) * s
    return s

def forecast_monthly_spend(
    normalized_rows: List[dict],
    target_month: MonthKey,
    cfg: BudgetingCfg,
) -> float:
    """
    Build a robust monthly spend forecast using:
      - monthly totals over a recency window (EWMA)
      - optional seasonal anchor (same month last year)
      - robust outlier handling
    """
    totals = monthly_living_totals(
        normalized_rows,
        use_your_share=cfg.use_your_share,
        exclude_buckets=cfg.exclude_buckets,
    )

    # months strictly before target_month within window
    all_months = _sort_month_keys([m for m in totals.keys() if m < target_month])
    if cfg.window_months > 0:
        all_months = all_months[-cfg.window_months :]

    series = [totals[m] for m in all_months]
    if len(series) < max(1, cfg.min_months) and series:
        # not enough history; just use mean
        return sum(series) / len(series) if series else 0.0

    # outlier treatment
    cleaned: List[float]
    if cfg.outlier_method == "winsor":
        cleaned = winsorize(series, cfg.outlier_k)
    else:
        # default MAD filter (drop outliers)
        keep = remove_outliers_mad(series, cfg.outlier_k)
        cleaned = keep if keep else series  # fallback if all dropped

    # EWMA on time-order
    ewma = _ewma(cleaned, cfg.ewma_alpha)

    # seasonal anchor (same month last year), if present
    anchor_key = _ym_to_prev_year_same_month(target_month)
    anchor_val = totals.get(anchor_key)

    if anchor_val is not None and cfg.seasonal_weight > 0.0:
        baseline = (1.0 - cfg.seasonal_weight) * ewma + cfg.seasonal_weight * anchor_val
    else:
        baseline = ewma

    return max(baseline, 0.0)

def compute_weekly_spending_schedule(
    month: MonthKey,
    monthly_spend_budget: float,
    start_weekday: str = "MON",
) -> List[WeeklyAllowance]:
    weeks = compute_weeks_in_month(month, start_weekday)
    if not weeks:
        return []

    # even split with penny-fairness to early weeks
    per = round(monthly_spend_budget / len(weeks), 2)
    schedule = [WeeklyAllowance(w.week_start, w.week_end, per) for w in weeks]
    remainder = round(monthly_spend_budget - per * len(weeks), 2)
    i = 0
    while remainder > 0 and i < len(schedule):
        bump = min(0.01, remainder)
        schedule[i].allowance = round(schedule[i].allowance + bump, 2)
        remainder = round(remainder - bump, 2)
        i += 1
    return schedule
