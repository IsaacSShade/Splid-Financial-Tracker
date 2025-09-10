from __future__ import annotations
import csv
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Iterable

def ensure_dir(p: Path):
  p.mkdir(parents=True, exist_ok=True)

def summarize_month(rows: List[dict]) -> dict:
  """Return living_total, per-bucket totals."""
  living_total = 0.0
  per_bucket = defaultdict(float)
  for r in rows:
    if r["is_payment"]:
      continue
    living_total += r["your_share"]
    per_bucket[r["bucket"]] += r["your_share"]
  return {"living_total": round(living_total,2),
          "per_bucket": {k: round(v,2) for k,v in per_bucket.items()}}

def write_month_csv(out_dir: Path, month: str, rows: List[dict]):
  ensure_dir(out_dir)
  path = out_dir / f"month={month}.csv"
  fieldnames = ["date","month","title","payer","category_raw","bucket","amount_total","your_share","is_payment"]
  with path.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    for r in rows:
      w.writerow({k: r[k] for k in fieldnames})

def upsert_monthly_summary(data_dir: Path, month: str, income: float, living_total: float, per_bucket: Dict[str,float], extra: Dict[str, float] | None = None):
  ensure_dir(data_dir)
  path = data_dir / "monthly_summary.csv"
  # load existing
  rows: List[dict] = []
  if path.exists():
    with path.open("r", newline="", encoding="utf-8") as f:
      rows = list(csv.DictReader(f))

  # compute split
  excess = max(0.0, income - living_total)
  savings = round(0.5 * excess, 2)
  spending = round(excess - savings, 2)

  # flatten buckets (keep a stable subset + dynamic)
  base = {
    "month": month,
    "income": f"{income:.2f}",
    "living_total": f"{living_total:.2f}",
    "excess": f"{excess:.2f}",
    "savings_allowance": f"{savings:.2f}",
    "spending_allowance": f"{spending:.2f}",
  }
  extra = extra or {}
  out = base.copy()
  # include common buckets if present
  for k, v in per_bucket.items():
    if v != 0.0:
      out[k] = f"{v:.2f}"
  # include extra computed fields like , house_on_card, etc.
  for k, v in extra.items():
    if v != 0.0:
      out[k] = f"{float(v):.2f}"

  # upsert by month
  rows = [r for r in rows if r.get("month") != month]
  rows.append(out)
  # sort by month
  rows.sort(key=lambda r: r["month"])

  # unify fieldnames
  all_fields = list(base.keys())
  dynamic = sorted({k for r in rows for k in r.keys()} - set(all_fields))
  fieldnames = all_fields + dynamic

  with path.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    for r in rows:
      # fill missing
      for k in fieldnames:
        r.setdefault(k, "")
      w.writerow(r)

def write_month_md(reports_dir: Path, month: str, income: float, living_total: float, per_bucket: Dict[str,float]):
  ensure_dir(reports_dir)
  path = reports_dir / f"{month}.md"

  lines = []
  lines.append(f"# {month} — Your Monthly Budget Summary\n")
  lines.append("> All amounts below are **your share only**. Splid settle-up “Payment” rows are excluded.\n")

  # Always show living cost
  lines.append(f"- **Your overall living cost (all buckets):** ${living_total:,.2f}")

  # Only show income-based lines if income > 0
  if income > 0:
    excess = max(0.0, income - living_total)
    savings = 0.5 * excess
    spending = excess - savings
    lines.append(f"- **Your income:** ${income:,.2f}")
    lines.append(f"- **Excess (income - living):** ${excess:,.2f}")
    lines.append(f"- **Savings (50% of excess):** ${savings:,.2f}")
    lines.append(f"- **Spending (50% of excess):** ${spending:,.2f}")

  lines.append("")  # spacer

  if per_bucket:
    lines.append("## Breakdown — your share by bucket\n")
    for k in sorted(per_bucket.keys()):
      lines.append(f"- **{k}**: ${per_bucket[k]:,.2f}")
    lines.append("")

  path.write_text("\n".join(lines), encoding="utf-8")

def write_overall_trends_md(reports_dir: Path, monthly_summary_path: Path):
  ensure_dir(reports_dir)
  if not monthly_summary_path.exists():
    return
  import csv
  rows = list(csv.DictReader(monthly_summary_path.open("r", encoding="utf-8")))
  if not rows:
    return

  def f(r, k):
    try:
      return float(r.get(k, "") or 0.0)
    except Exception:
      return 0.0

  n_all = len(rows)
  rows_with_income = [r for r in rows if f(r, "income") > 0.0]
  n_income = len(rows_with_income)

  # Averages
  avg_living_all = (sum(f(r, "living_total") for r in rows) / n_all) if n_all else 0.0
  avg_income_inc = (sum(f(r, "income") for r in rows_with_income) / n_income) if n_income else None
  avg_excess_inc = (sum(f(r, "excess") for r in rows_with_income) / n_income) if n_income else None

  lines = []
  lines.append("# Overall Trends\n")
  lines.append(f"- **Months covered:** {n_all}")

  # Income/excess averaged over months with income only
  if n_income:
    lines.append(f"- **Your Average Income:** ${avg_income_inc:,.2f}")
    lines.append(f"- **Your Average Excess:** ${avg_excess_inc:,.2f}")
  else:
    lines.append(f"- **Your Average Income:** —  _(no months with income)_")
    lines.append(f"- **Your Average Excess:** —  _(no months with income)_")

  # Living cost is independent of income; keep across all months
  lines.append(f"- **Your Average Living Cost:** ${avg_living_all:,.2f}\n")

  # ---- Buckets / Extras (unchanged from your current version) ----
  base_fields = {
      "month", "income", "living_total", "excess",
      "savings_allowance", "spending_allowance"
  }
  extras_display = {
      "house_on_card": "House charges on card (matched)",
      "fun_spend_card": "Personal spending on card (unmatched)",
      "personal_spend_card": "Personal spending on card",
  }
  alias_bucket = {"-": "uncategorized", "–": "uncategorized"}

  all_keys = set(k for r in rows for k in r.keys())
  dynamic_keys = sorted(all_keys - base_fields)

  # Buckets averaged over ALL months (you can change to income-only if you want)
  bucket_sums = {}
  for key in dynamic_keys:
    if key in extras_display:
      continue
    canon = alias_bucket.get(key, key)
    bucket_sums[canon] = bucket_sums.get(canon, 0.0) + sum(f(r, key) for r in rows)
  bucket_avgs = {k: (v / n_all) for k, v in bucket_sums.items() if v > 0.0}

  lines.append("## Buckets (averages per month)\n")
  for b, avg_val in sorted(bucket_avgs.items(), key=lambda kv: kv[1], reverse=True):
    lines.append(f"- {b}: ${avg_val:,.2f}")

  # Extras: if you want them averaged only over months with data, swap this block later
  extras_avgs = {}
  for raw_key, label in extras_display.items():
    if raw_key in dynamic_keys:
      total = sum(f(r, raw_key) for r in rows)
      if total > 0.0:
        extras_avgs[label] = total / n_all

  if extras_avgs:
    lines.append("\n## Other indicators (averages per month)\n")
    for label, avg_val in sorted(extras_avgs.items(), key=lambda kv: kv[1], reverse=True):
      lines.append(f"- {label}: ${avg_val:,.2f}")

  (reports_dir / "overall_trends.md").write_text("\n".join(lines), encoding="utf-8")

  
# --- Extra section writers ---

def write_weekly_schedule_section(
  reports_dir: Path,
  month: str,
  weekly_sched: Iterable,            # items with week_start, week_end, allowance
  *,
  meta: dict,                         # method + inputs for the explainer
) -> None:
  """
  Appends a self-contained 'Weekly spending plan' section to <reports_dir>/<month>.md.
  Only call this when the month has income > 0.
  """
  ensure_dir(reports_dir)
  path = reports_dir / f"{month}.md"

  forecast = float(meta.get("forecast_basis_usd", 0.0))
  week_start = str(meta.get("week_start", "MON"))
  ewma_alpha = meta.get("ewma_alpha", None)
  seasonal_weight = meta.get("seasonal_weight", None)
  window_months = meta.get("window_months", None)
  outlier_method = meta.get("outlier_method", None)
  outlier_k = meta.get("outlier_k", None)
  exclude_buckets = meta.get("exclude_buckets") or []

  lines = []
  lines.append("")  # spacer
  lines.append("## Weekly spending plan\n")
  lines.append(
    f"_What this is:_ A planning target that splits your **forecasted discretionary spend for {month} "
    f"(${forecast:,.2f})** evenly across calendar weeks starting **{week_start}**.\n"
  )
  lines.append(
    "_How it’s estimated:_ recency-weighted average (EWMA"
    + (f", α={ewma_alpha}" if ewma_alpha is not None else "")
    + (f", window≈{window_months} mo" if window_months is not None else "")
    + "), seasonal anchor to the **same month last year**"
    + (f" (weight={seasonal_weight})" if seasonal_weight is not None else " (if available)")
    + ", and outlier handling"
    + (f" ({outlier_method}, k={outlier_k})" if outlier_method is not None else "")
    + "."
  )
  lines.append(
    "Excluded buckets from this forecast: "
    + (", ".join(exclude_buckets) if exclude_buckets else "none")
    + ".\n"
  )

  # Render as a table (clearer than bullets)
  lines.append("| Week start | Week end | Allowance |")
  lines.append("|---|---|---:|")
  for w in weekly_sched:
    lines.append(f"| {w.week_start.isoformat()} | {w.week_end.isoformat()} | ${w.allowance:,.2f} |")
  lines.append("")

  with path.open("a", encoding="utf-8") as f:
    f.write("\n".join(lines))

def write_card_summary_section(reports_dir: Path, month: str, *, house_on_card: float, personal_spend_card: float) -> None:
  """
  Appends a credit card spending panel for the month.
  - 'house_on_card' = charges that matched house expenses in Splid (shared/living)
  - 'personal_spend_card' = charges that did NOT match house expenses (personal)
  """
  ensure_dir(reports_dir)
  path = reports_dir / f"{month}.md"
  total_card_purchases = round(house_on_card + personal_spend_card, 2)

  lines = []
  lines.append("")  # spacer
  lines.append("## Credit card spending\n")
  lines.append(f"- **Total card purchases:** ${total_card_purchases:,.2f}")
  lines.append(f"  - Matched to house expenses: ${house_on_card:,.2f}")
  lines.append(f"  - Personal (unmatched): ${personal_spend_card:,.2f}")
  lines.append("")
  with path.open("a", encoding="utf-8") as f:
    f.write("\n".join(lines))
