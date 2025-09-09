from __future__ import annotations
import csv
from pathlib import Path
from collections import defaultdict
from typing import Dict, List

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
  for k,v in per_bucket.items():
    out[k] = f"{v:.2f}"
  # include extra computed fields like fun_spend_card, house_on_card, etc.
  for k, v in extra.items():
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
  excess = max(0.0, income - living_total)
  savings = 0.5 * excess
  spending = excess - savings

  lines = []
  lines.append(f"# {month} — Your Monthly Budget Summary\n")
  lines.append("> All amounts below are **your share only**. Splid settle-up “Payment” rows are excluded.\n")
  lines.append(f"- **Your income:** ${income:,.2f}")
  lines.append(f"- **Your overall living cost (all buckets):** ${living_total:,.2f}")
  lines.append(f"- **Excess (income - living):** ${excess:,.2f}")
  lines.append(f"- **Savings (50% of excess):** ${savings:,.2f}")
  lines.append(f"- **Spending (50% of excess):** ${spending:,.2f}\n")
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
  import csv, statistics as stats
  rows = list(csv.DictReader(monthly_summary_path.open("r", encoding="utf-8")))
  if not rows:
    return

  def f(r,k): 
    try: return float(r.get(k,"") or 0.0)
    except: return 0.0

  income = [f(r,"income") for r in rows]
  living = [f(r,"living_total") for r in rows]
  excess = [f(r,"excess") for r in rows]

  avg_income = sum(income)/len(income)
  avg_living = sum(living)/len(living)
  avg_excess = sum(excess)/len(excess)

  lines = []
  lines.append("# Overall Trends\n")
  lines.append(f"- **Months covered:** {len(rows)}")
  lines.append(f"- **Your Average Income:** ${avg_income:,.2f}")
  lines.append(f"- **Your Average Living Cost:** ${avg_living:,.2f}")
  lines.append(f"- **Your Average Excess:** ${avg_excess:,.2f}\n")
  # show most common buckets
  known = {"rent","utilities","groceries","house_supplies","house_bills","uncategorized"}
  buckets = sorted({k for r in rows for k in r.keys() if k not in {"month","income","living_total","excess","savings_allowance","spending_allowance"}})
  lines.append("## Buckets (averages per month)\n")
  for b in buckets:
    vals = [f(r,b) for r in rows]
    if any(vals):
      lines.append(f"- {b}: ${sum(vals)/len(vals):,.2f}")
  (reports_dir / "overall_trends.md").write_text("\n".join(lines), encoding="utf-8")
