from __future__ import annotations
from datetime import date, timedelta

_DOW = {"MON":0, "TUE":1, "WED":2, "THU":3, "FRI":4, "SAT":5, "SUN":6}

def _first_day(year:int, month:int) -> date:
    return date(year, month, 1)

def _last_day(year:int, month:int) -> date:
    n = 31
    while True:
        try:
            return date(year, month, n)
        except ValueError:
            n -= 1

def weeks_for_month(month: str, start_day: str = "MON"):
    y, m = map(int, month.split("-"))
    f = _first_day(y, m)
    l = _last_day(y, m)
    start_dow = _DOW.get(start_day.upper(), 0)
    # find first week-start on/after the 1st
    d = f
    while d.weekday() != start_dow:
        d += timedelta(days=1)
    weeks = []
    while d <= l:
        end = d + timedelta(days=6)
        end = min(end, l)
        weeks.append((d, end))
        d = end + timedelta(days=1)
        while d.weekday() != start_dow and d <= l:
            d += timedelta(days=1)
    return weeks

def split_allowance(month: str, spending_allowance: float, start_day: str = "MON", rollover: bool = True):
    wk = weeks_for_month(month, start_day)
    if not wk:
        return []
    # equal split across N weeks; rollover is for runtime tracking, not needed now
    per = round(spending_allowance / len(wk), 2)
    schedule = [{"week_start": a.isoformat(), "week_end": b.isoformat(), "allowance": per} for (a,b) in wk]
    # distribute any rounding pennies to earliest weeks
    remainder = round(spending_allowance - per*len(wk), 2)
    i = 0
    while remainder > 0 and i < len(schedule):
        bump = min(0.01, remainder)
        schedule[i]["allowance"] = round(schedule[i]["allowance"] + bump, 2)
        remainder = round(remainder - bump, 2)
        i += 1
    return schedule
