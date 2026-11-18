"""Attack success rate with a 95% Wilson interval, plus the small tables the runner prints."""

import math
from collections import defaultdict


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def summarize(records: list[dict]) -> list[dict]:
    """One row per (config, category): attack success rate for attacks, pass rate for benign."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in records:
        groups[(r["config"], r["kind"], r["category"])].append(r)
    rows = []
    for (config, kind, category), items in sorted(groups.items()):
        wins = sum(1 for r in items if r["outcome"])
        lo, hi = wilson(wins, len(items))
        rows.append(
            {
                "config": config,
                "kind": kind,
                "category": category,
                "n": len(items),
                "rate": wins / len(items),
                "ci_low": lo,
                "ci_high": hi,
                "blocked": sum(1 for r in items if r["blocked"]) / len(items),
            }
        )
    return rows
