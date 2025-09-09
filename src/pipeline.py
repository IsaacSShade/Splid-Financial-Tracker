from __future__ import annotations
from pathlib import Path
from datetime import date
from collections import defaultdict

from config import load_configs
from splid_xls import parse_splid_xls
from normalize import normalize_rows
from months import months_present, previous_complete_month
from income import monthly_income
from reports import (
    summarize_month,
    write_month_csv,
    upsert_monthly_summary,
    write_month_md,
    write_overall_trends_md,
)
from pathlib import Path
from glob import glob
from boa_pdf import parse_statement_pdf
from cc_calendarize import calendarize
from match_cc_to_splid import exact_match
from weekly import split_allowance
import json

def _find_latest_splid_xls(splid_dir: Path) -> Path:
    candidates = sorted([p for p in splid_dir.glob("*.xls") if p.is_file()],
                        key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError(f"No Splid .xls files found in {splid_dir}")
    return candidates[0]

def run_pipeline(inputs_dir: Path, config_dir: Path, data_dir: Path, reports_dir: Path):
  cfg = load_configs(config_dir)
  with (config_dir / "cc_match.json").open("r", encoding="utf-8") as f:
    cc_match = json.load(f)
  with (config_dir / "cc_sources.json").open("r", encoding="utf-8") as f:
    cc_src = json.load(f)

  # 1) Read latest Splid XML (contains all time)
  splid_dir = inputs_dir / "splid"
  xml_path = _find_latest_splid_xls(splid_dir)

  raw_rows = parse_splid_xls(xml_path, your_name=cfg.you.name)
  rows = normalize_rows(raw_rows, cfg.bucket)

  # 2) Decide which months to process
  all_months = months_present(rows)
  target_months = list(all_months)

  if cfg.options.overrideMonth:
    target_months = [cfg.options.overrideMonth]
  elif not cfg.options.backfillAll:
    if cfg.options.monthSelection == "previous_complete":
      target_months = [previous_complete_month(date.today())]
    else:  # latest_any
      target_months = [all_months[-1]] if all_months else []

  if not target_months:
    print("No months found to process.")
    return

  # 3) Process months
  rows_by_month = defaultdict(list)
  for r in rows:
    rows_by_month[r["month"]].append(r)
    
  pdf_glob = cc_src.get("pdfStatementsGlob", "inputs/bank/boa_statements/*.pdf")
  pdf_paths = [Path(p) for p in glob(str(config_dir.parent / pdf_glob))]
  cc_rows_all = []
  for p in pdf_paths:
      try:
          cc_rows_all += parse_statement_pdf(p)
      except Exception as e:
          print(f"[WARN] Failed to parse {p.name}: {e}")
  # Calendarize by month (posting date by default)
  cal_by_month = calendarize(cc_rows_all, use_post_date=cc_src.get("usePostingDateForMonth", True))

  for m in target_months:
    month_rows = rows_by_month.get(m, [])
    if not month_rows:
      continue

    # write per-month normalized CSV
    write_month_csv(data_dir, m, month_rows)

    # living + buckets
    summary = summarize_month(month_rows)
    living_total = summary["living_total"]
    per_bucket = summary["per_bucket"]

    # income
    income = monthly_income(m, cfg.income)
    
    # Card charges for this month (if any)
    cc_rows_m = cal_by_month.get(m, [])

    matched, unmatched = exact_match(
        cc_rows_m,
        [r for r in month_rows if not r["is_payment"]],
        cfg.you.name,
        amount_tol_cents=int(cc_match.get("amountToleranceCents", 0)),
        date_window_days=int(cc_match.get("dateWindowDays", 0)),
        only_if_payer_is_you=bool(cc_match.get("onlyIfPayerIsYou", True))
    )

    house_on_card = round(sum(r.amount for r in matched), 2)
    fun_spend_card = round(sum(r.amount for r in unmatched if r.section == "purchases_adjustments"), 2)
    
    # Weekly schedule from spending allowance (equal split across Mondays)
    excess = max(0.0, income - living_total)
    spending_allowance = round(0.5 * excess, 2)
    weekly_sched = split_allowance(m, spending_allowance, start_day="MON", rollover=True)

    # summary row & markdown
    upsert_monthly_summary(
      data_dir, m, income, living_total, per_bucket,
      extra={"fun_spend_card": fun_spend_card, "house_on_card": house_on_card}
    )
    write_month_md(reports_dir, m, income, living_total, per_bucket)
    
    # Append card + weekly panel to the month report
    md_path = reports_dir / f"{m}.md"
    extra_lines = []
    extra_lines.append("## Card spend (your BoA card)\n")
    extra_lines.append(f"- House on card (matched to Splid, exact): ${house_on_card:,.2f}")
    extra_lines.append(f"- Fun spend (unmatched card charges): ${fun_spend_card:,.2f}\n")
    extra_lines.append("## Weekly spending allowance\n")
    for w in weekly_sched:
        extra_lines.append(f"- {w['week_start']} → {w['week_end']}: ${w['allowance']:.2f}")
    extra_lines.append("")
    with md_path.open("a", encoding="utf-8") as f:
        f.write("\n".join(extra_lines))

  # 4) overall trends page
  write_overall_trends_md(reports_dir, data_dir / "monthly_summary.csv")

  print(f"Processed months: {', '.join(target_months)}")
