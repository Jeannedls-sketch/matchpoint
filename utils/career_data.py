"""
Real LBS Career Centre data — used to GROUND Matchpoint's suggestions in
actual student outcomes, instead of relying only on the model's judgment.

Sources (provided by the Career Centre, Spring 2026 workshop):
- gm_offers.csv: 800 real MiM/MFA/MAM offers, 2023-2025 (title, employer, city)
- typical_career_paths.csv: 80 real entry-role -> next-step -> transition paths

This mirrors what the "Charlotte" n8n version does in its Workflow 2 (scoring
against real data) — but surfaced live in the app, not in a spreadsheet.
"""

import csv
import os

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

_offers_cache = None
_paths_cache = None


def _load_offers():
    global _offers_cache
    if _offers_cache is None:
        path = os.path.join(_DATA_DIR, "gm_offers.csv")
        with open(path, encoding="utf-8") as f:
            _offers_cache = list(csv.DictReader(f))
    return _offers_cache


def _load_paths():
    global _paths_cache
    if _paths_cache is None:
        path = os.path.join(_DATA_DIR, "typical_career_paths.csv")
        with open(path, encoding="utf-8") as f:
            _paths_cache = list(csv.DictReader(f))
    return _paths_cache


def find_real_offers(keywords: list, limit: int = 8) -> list:
    """
    Search the real 2023-2025 offers dataset for rows whose job_title,
    employer, or industry contains any of `keywords` (case-insensitive).
    Returns up to `limit` matching real placements, most recent first.

    This is used to show "real LBS graduates were hired here" examples —
    genuine social proof, not invented.
    """
    if not keywords:
        return []
    kws = [k.lower() for k in keywords if k]
    offers = _load_offers()
    matches = []
    for row in offers:
        haystack = f"{row.get('job_title','')} {row.get('employer','')} {row.get('industry','')} {row.get('program','')}".lower()
        if any(kw in haystack for kw in kws):
            matches.append(row)
    # most recent grad year first
    matches.sort(key=lambda r: r.get("grad_year", ""), reverse=True)
    return matches[:limit]


def find_career_paths(keywords: list, limit: int = 5) -> list:
    """
    Search the 80-row typical-career-paths table for sectors/entry roles
    matching any of `keywords`. Returns matching rows with next steps and
    further transitions — real structured guidance, not generated.
    """
    if not keywords:
        return []
    kws = [k.lower() for k in keywords if k]
    paths = _load_paths()
    matches = []
    for row in paths:
        haystack = f"{row.get('sector','')} {row.get('entry_role','')}".lower()
        if any(kw in haystack for kw in kws):
            matches.append(row)
    return matches[:limit]


def offers_summary_stats(keywords: list) -> dict:
    """Quick aggregate: how many real matching offers exist, and in which cities/employers most often."""
    matches = find_real_offers(keywords, limit=1000)
    if not matches:
        return {"count": 0}
    from collections import Counter
    employers = Counter(m["employer"] for m in matches if m.get("employer"))
    cities = Counter(m["city"] for m in matches if m.get("city"))
    return {
        "count": len(matches),
        "top_employers": [e for e, _ in employers.most_common(5)],
        "top_cities": [c for c, _ in cities.most_common(3)],
    }
