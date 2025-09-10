from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
if str(SRC) not in sys.path:
  sys.path.insert(0, str(SRC))

from config.loader import load_unified_config
from pipeline import run_pipeline

def main():
  cfg = load_unified_config(REPO)
  run_pipeline(cfg=cfg)

if __name__ == "__main__":
  main()
