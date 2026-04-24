"""
GEO Benchmark store — percentile distributions by vertical.

Provides context for a prospect's score relative to peers.
"""

import json
from pathlib import Path
from typing import Optional

# Default percentile distributions (synthetic, seeded from scan experience)
# Each entry maps overall_score → cumulative percentile (0-100)
# Interpolated linearly between points.
DEFAULT_DISTRIBUTIONS = {
    "professional_services": {
        "description": "Law firms, consultancies, agencies",
        "points": [
            [1.0, 5],
            [2.0, 15],
            [3.0, 30],
            [4.0, 50],
            [5.0, 70],
            [6.0, 85],
            [7.0, 93],
            [8.0, 97],
            [9.0, 99],
            [10.0, 100],
        ],
    },
    "dtc": {
        "description": "DTC / eCommerce ($100M+)",
        "points": [
            [1.0, 3],
            [2.0, 10],
            [3.0, 22],
            [4.0, 40],
            [5.0, 58],
            [6.0, 75],
            [7.0, 88],
            [8.0, 95],
            [9.0, 99],
            [10.0, 100],
        ],
    },
    "saas": {
        "description": "SaaS / B2B tech",
        "points": [
            [1.0, 2],
            [2.0, 8],
            [3.0, 18],
            [4.0, 32],
            [5.0, 48],
            [6.0, 65],
            [7.0, 80],
            [8.0, 91],
            [9.0, 97],
            [10.0, 100],
        ],
    },
    "default": {
        "description": "All sites (fallback)",
        "points": [
            [1.0, 5],
            [2.0, 15],
            [3.0, 28],
            [4.0, 45],
            [5.0, 62],
            [6.0, 78],
            [7.0, 89],
            [8.0, 95],
            [9.0, 99],
            [10.0, 100],
        ],
    },
}

BENCHMARKS_PATH = Path(__file__).parent / "benchmarks.json"


def _load() -> dict:
    if BENCHMARKS_PATH.exists():
        try:
            return json.loads(BENCHMARKS_PATH.read_text())
        except Exception:
            pass
    return dict(DEFAULT_DISTRIBUTIONS)


def _save(data: dict):
    BENCHMARKS_PATH.write_text(json.dumps(data, indent=2))


def _normalize_vertical(vertical: str) -> str:
    v = vertical.lower().strip().replace(" ", "_").replace("/", "_")
    mapping = {
        "professional_services": ["professional_services", "law", "legal", "consulting", "agency", "agencies"],
        "dtc": ["dtc", "ecommerce", "e_commerce", "retail", "consumer"],
        "saas": ["saas", "b2b", "tech", "software"],
    }
    for canonical, aliases in mapping.items():
        if v in aliases:
            return canonical
    return "default"


def get_percentile(score: float, vertical: str = "default") -> int:
    """Return the percentile (0-100) for a given score within a vertical."""
    data = _load()
    key = _normalize_vertical(vertical)
    dist = data.get(key, data.get("default", DEFAULT_DISTRIBUTIONS["default"]))
    points = dist["points"]

    # Clamp
    if score <= points[0][0]:
        return int(points[0][1])
    if score >= points[-1][0]:
        return int(points[-1][1])

    # Linear interpolation
    for i in range(len(points) - 1):
        x0, y0 = points[i]
        x1, y1 = points[i + 1]
        if x0 <= score <= x1:
            if x1 == x0:
                return int(y0)
            pct = y0 + (score - x0) * (y1 - y0) / (x1 - x0)
            return int(round(pct))
    return 50


def get_vertical_label(vertical: str) -> str:
    key = _normalize_vertical(vertical)
    data = _load()
    dist = data.get(key, data.get("default", DEFAULT_DISTRIBUTIONS["default"]))
    return dist.get("description", key.replace("_", " ").title())


def update_distribution(vertical: str, score: float):
    """
    Record a new score observation into the benchmark store.
    This should be called after each scan to gradually build
    real distributions from your prospect pool.
    """
    data = _load()
    key = _normalize_vertical(vertical)
    if key not in data:
        data[key] = {"description": key.replace("_", " ").title(), "raw_scores": []}

    raw = data[key].setdefault("raw_scores", [])
    raw.append(round(score, 2))
    # Keep last 500 observations
    if len(raw) > 500:
        raw = raw[-500:]
    data[key]["raw_scores"] = raw

    # Rebuild percentile points from raw scores
    if len(raw) >= 10:
        sorted_scores = sorted(raw)
        n = len(sorted_scores)
        new_points = []
        for target_pct in range(10, 101, 10):
            idx = int((target_pct / 100) * (n - 1))
            val = sorted_scores[min(idx, n - 1)]
            new_points.append([round(val, 1), target_pct])
        data[key]["points"] = new_points

    _save(data)
