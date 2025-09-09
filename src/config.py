from __future__ import annotations
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class YouCfg:
  name: str

@dataclass
class IncomeCfg:
  hourlyRate: float
  defaultWeeklyHours: float
  startDate: str               # YYYY-MM-DD
  hoursOverrides: Dict[str, float]  # {"YYYY-MM": totalHours}

@dataclass
class OptionsCfg:
  monthSelection: str          # "previous_complete" | "latest_any"
  overrideMonth: str           # "" or "YYYY-MM"
  backfillAll: bool
  carryoverMode: str           # "none" | "bank_csv"

@dataclass
class BucketMapCfg:
  titleToBucket: Dict[str, str]       # regex (case-insens) -> bucket
  categoryToBucket: Dict[str, str]    # exact category -> bucket
  paymentTitleExact: list[str]

@dataclass
class AllConfigs:
  you: YouCfg
  income: IncomeCfg
  options: OptionsCfg
  bucket: BucketMapCfg

def _load_json(path: Path):
  with path.open("r", encoding="utf-8") as f:
    return json.load(f)

def load_configs(config_dir: Path) -> AllConfigs:
  you = _load_json(config_dir / "you.json")
  income = _load_json(config_dir / "income.json")
  options = _load_json(config_dir / "options.json")
  bucket = _load_json(config_dir / "bucket_map.json")

  return AllConfigs(
    you=YouCfg(name=you["name"]),
    income=IncomeCfg(
      hourlyRate=float(income["hourlyRate"]),
      defaultWeeklyHours=float(income["defaultWeeklyHours"]),
      startDate=income["startDate"],
      hoursOverrides={k: float(v) for k,v in income.get("hoursOverrides", {}).items()}
    ),
    options=OptionsCfg(
      monthSelection=options["monthSelection"],
      overrideMonth=options.get("overrideMonth",""),
      backfillAll=bool(options["backfillAll"]),
      carryoverMode=options["carryoverMode"]
    ),
    bucket=BucketMapCfg(
      titleToBucket=bucket.get("titleToBucket", {}),
      categoryToBucket=bucket.get("categoryToBucket", {}),
      paymentTitleExact=bucket.get("paymentTitleExact", ["Payment"])
    ),
  )
