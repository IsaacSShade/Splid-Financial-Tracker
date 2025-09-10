from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from core.models import BudgetingCfg

@dataclass
class YouCfg:
  name: str

@dataclass
class IncomeCfg:
  hourly_rate: float
  default_weekly_hours: float
  start_date: str
  hours_overrides: Dict[str, float]

@dataclass
class OptionsCfg:
  month_selection: str
  override_month: str
  backfill_all: bool
  carryover_mode: str

@dataclass
class BucketMapCfg:
  title_to_bucket: Dict[str, str]
  category_to_bucket: Dict[str, str]
  payment_title_exact: list[str]

@dataclass
class CCSourcesCfg:
  pdf_statements_glob: str
  use_posting_date_for_month: bool

@dataclass
class CCMatchCfg:
  amount_tolerance_cents: int
  date_window_days: int
  only_if_payer_is_you: bool

@dataclass
class PathsCfg:
  inputs_dir: Path
  data_dir: Path
  reports_dir: Path
  config_dir: Path

@dataclass
class UnifiedConfig:
  you: YouCfg
  income: IncomeCfg
  options: OptionsCfg
  bucket: BucketMapCfg
  cc_sources: CCSourcesCfg
  cc_match: CCMatchCfg
  paths: PathsCfg
  budgeting: BudgetingCfg

def load_unified_config(repo_root: Path) -> UnifiedConfig:
    """Load config/settings.yaml only. No JSON fallbacks."""
    cfg_dir = repo_root / "config"
    yaml_cfg = cfg_dir / "settings.yaml"

    # Require PyYAML
    try:
        import yaml  # type: ignore
    except Exception as e:
        raise ImportError(
            "PyYAML is required to read config/settings.yaml. Install with: pip install pyyaml"
        ) from e

    if not yaml_cfg.exists():
        raise FileNotFoundError(
            f"Missing {yaml_cfg}. Create it (see the settings.yaml template you set up)."
        )

    y: Dict[str, Any] = yaml.safe_load(yaml_cfg.read_text(encoding="utf-8")) or {}

    # minimal structure checks (fail fast with clear messages)
    for section in ["user", "paths", "options", "income", "buckets", "credit_card"]:
        if section not in y:
            raise KeyError(f"settings.yaml is missing the '{section}' section")

    user = y["user"]
    paths = y["paths"]
    options = y["options"]
    income = y["income"]
    buckets = y["buckets"]
    cc = y["credit_card"]
    budgeting = y.get("budgeting", {})

    return UnifiedConfig(
        you=YouCfg(name=user["name"]),
        income=IncomeCfg(
            hourly_rate=float(income["hourly_rate"]),
            default_weekly_hours=float(income["default_weekly_hours"]),
            start_date=str(income["start_date"]),
            hours_overrides={str(k): float(v) for k, v in income.get("hours_overrides", {}).items()},
        ),
        options=OptionsCfg(
            month_selection=str(options["month_selection"]),
            override_month=str(options.get("override_month", "")),
            backfill_all=bool(options["backfill_all"]),
            carryover_mode=str(options["carryover_mode"]),
        ),
        bucket=BucketMapCfg(
            title_to_bucket=buckets.get("title_to_bucket", {}),
            category_to_bucket=buckets.get("category_to_bucket", {}),
            payment_title_exact=buckets.get("payment_title_exact", ["Payment"]),
        ),
        cc_sources=CCSourcesCfg(
            pdf_statements_glob=str(cc["sources"]["pdf_statements_glob"]),
            use_posting_date_for_month=bool(cc["sources"]["use_posting_date_for_month"]),
        ),
        cc_match=CCMatchCfg(
            amount_tolerance_cents=int(cc["matching"]["amount_tolerance_cents"]),
            date_window_days=int(cc["matching"]["date_window_days"]),
            only_if_payer_is_you=bool(cc["matching"]["only_if_payer_is_you"]),
        ),
        paths=PathsCfg(
            inputs_dir=(repo_root / paths["inputs_dir"]).resolve(),
            data_dir=(repo_root / paths["data_dir"]).resolve(),
            reports_dir=(repo_root / paths["reports_dir"]).resolve(),
            config_dir=cfg_dir.resolve(),
        ),
        budgeting=BudgetingCfg(**budgeting),
    )