from __future__ import annotations
from pathlib import Path
from datetime import date
from collections import defaultdict
from pathlib import Path
from glob import glob

from reports import (
  summarize_month,
  write_card_summary_section,
  write_month_csv,
  upsert_monthly_summary,
  write_month_md,
  write_overall_trends_md,
  write_weekly_schedule_section,
)
from config.loader import UnifiedConfig
from budgeting.weekly_budget import (
    forecast_monthly_spend,
    compute_weekly_spending_schedule,
)
from ingest.splid import parse_splid_xls
from analytics.periods import months_present
from core.dates import previous_complete_month
from budgeting.income import monthly_income       # (or rename to calculate_monthly_income later)
from ingest.cards.bofa import parse_statement_pdf
from analytics.cards import calendarize as calendarize_card_transactions
from analytics.card_matching import exact_match
from normalize import normalize_rows

def _find_latest_splid_xls(splid_dir: Path) -> Path:
    candidates = sorted([p for p in splid_dir.glob("*.xls") if p.is_file()],
                        key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError(f"No Splid .xls files found in {splid_dir}")
    return candidates[0]

def run_pipeline(cfg: UnifiedConfig):
  inputs_dir  = cfg.paths.inputs_dir
  data_dir    = cfg.paths.data_dir
  reports_dir = cfg.paths.reports_dir
  config_dir  = cfg.paths.config_dir

  # 1) Read latest Splid XML (contains all time)
  splid_dir = inputs_dir / "splid"
  xml_path = _find_latest_splid_xls(splid_dir)

  raw_rows = parse_splid_xls(xml_path, your_name=cfg.you.name)
  rows = normalize_rows(raw_rows, cfg.bucket)

  # 2) Decide which months to process
  all_months = months_present(rows)
  target_months = list(all_months)

  if cfg.options.override_month:
    target_months = [cfg.options.override_month]
  elif not cfg.options.backfill_all:
    if cfg.options.month_selection == "previous_complete":
      target_months = [previous_complete_month(date.today())]
    else:
      target_months = [all_months[-1]] if all_months else []

  if not target_months:
    print("No months found to process.")
    return

  # 3) Process months
  rows_by_month = defaultdict(list)
  for r in rows:
    rows_by_month[r["month"]].append(r)
    
  pdf_glob = cfg.cc_sources.pdf_statements_glob
  pdf_paths = [Path(p) for p in glob(str(config_dir.parent / pdf_glob))]
  cc_rows_all = []
  for p in pdf_paths:
      try:
          cc_rows_all += parse_statement_pdf(p)
      except Exception as e:
          print(f"[WARN] Failed to parse {p.name}: {e}")
  # Calendarize by month (posting date by default)
  cal_by_month = calendarize_card_transactions(cc_rows_all, use_post_date = cfg.cc_sources.use_posting_date_for_month)

  for month in target_months:
    month_rows = rows_by_month.get(month, [])
    if not month_rows:
      continue

    # write per-month normalized CSV
    write_month_csv(data_dir, month, month_rows)

    # living + buckets
    summary = summarize_month(month_rows)
    living_total = summary["living_total"]
    per_bucket = summary["per_bucket"]

    # income
    income = monthly_income(month, cfg.income)
    
    # Card charges for this month (if any)
    cc_rows_m = cal_by_month.get(month, [])

    matched, unmatched = exact_match(
      cc_rows_m,
      [r for r in month_rows if not r["is_payment"]],
      cfg.you.name,
      amount_tol_cents=cfg.cc_match.amount_tolerance_cents,
      date_window_days=cfg.cc_match.date_window_days,
      only_if_payer_is_you=cfg.cc_match.only_if_payer_is_you,
    )
    
    has_card_purchases = bool(matched or unmatched)

    if has_card_purchases:
      # Totals you want to display (exclude returns/credits from "spend")
      house_on_card = round(sum(c.amount for c in matched if c.amount > 0), 2)
      personal_spend_card = round(sum(c.amount for c in unmatched if c.amount > 0), 2)
    else:
      house_on_card = personal_spend_card = 0.0

    # summary row & markdown
    extra = {}
    if has_card_purchases and (house_on_card != 0.0 or personal_spend_card != 0.0):
      extra = {
          "house_on_card": house_on_card,
          "personal_spend_card": personal_spend_card,
      }

    upsert_monthly_summary(
        data_dir, month, income, living_total, per_bucket,
        extra=extra
    )
    write_month_md(reports_dir, month, income, living_total, per_bucket)
    if has_card_purchases and (house_on_card != 0.0 or personal_spend_card != 0.0):
      write_card_summary_section(
        reports_dir, month,
        house_on_card=house_on_card,
        personal_spend_card=personal_spend_card,
      )
    
    # Only show weekly plan in months where you had income
    if income > 0:
      forecasted_monthly_spend = forecast_monthly_spend(
        rows,   # normalized rows for all months
        month,  # "YYYY-MM"
        cfg.budgeting,
      )
      weekly_sched = compute_weekly_spending_schedule(
        month=month,
        monthly_spend_budget=forecasted_monthly_spend,
        start_weekday=cfg.budgeting.week_start,
      )
      write_weekly_schedule_section(
        reports_dir,
        month,
        weekly_sched,
        meta={
          "forecast_basis_usd": forecasted_monthly_spend,
          "week_start": cfg.budgeting.week_start,
          "ewma_alpha": cfg.budgeting.ewma_alpha,
          "seasonal_weight": cfg.budgeting.seasonal_weight,
          "window_months": cfg.budgeting.window_months,
          "outlier_method": cfg.budgeting.outlier_method,
          "outlier_k": cfg.budgeting.outlier_k,
          "exclude_buckets": cfg.budgeting.exclude_buckets or [],
        },
      )

  # 4) overall trends page
  write_overall_trends_md(reports_dir, data_dir / "monthly_summary.csv")

  print(f"Processed months: {', '.join(target_months)}")
