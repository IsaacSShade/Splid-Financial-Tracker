from pathlib import Path
import sys

# Make src/ importable no matter how you run it
REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pipeline import run_pipeline  # now a simple import

def main():
  inputs  = REPO / "inputs"
  config  = REPO / "config"
  data    = REPO / "data"
  reports = REPO / "reports"
  run_pipeline(inputs_dir=inputs, config_dir=config, data_dir=data, reports_dir=reports)

if __name__ == "__main__":
  main()
