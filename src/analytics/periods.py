from typing import List, Set


def months_present(rows) -> List[str]:
  ms: Set[str] = set(r["month"] for r in rows)
  return sorted(ms)