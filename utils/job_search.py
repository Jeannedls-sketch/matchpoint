"""
Fetches REAL job listings from Adzuna (https://developer.adzuna.com/).
Adzuna is a legitimate job-listing aggregator with a public API — unlike
scraping LinkedIn/Indeed (against their Terms of Service), this is an
authorized, legal source of real listings with real apply links.

Requires two env vars: ADZUNA_APP_ID and ADZUNA_APP_KEY (free to obtain).
"""

import os
import requests

BASE_URL = "https://api.adzuna.com/v1/api/jobs"

COUNTRY_CODES = {
    "United States": "us",
    "United Kingdom": "gb",
    "France": "fr",
    "Germany": "de",
    "Singapore": "sg",
    "Netherlands": "nl",
    "Canada": "ca",
    "Australia": "au",
}


def _get_credentials():
    app_id = os.environ.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        raise RuntimeError(
            "ADZUNA_APP_ID / ADZUNA_APP_KEY not set. Add them to your Streamlit secrets."
        )
    return app_id, app_key


def search_jobs(query: str, country_code: str, where: str = "", results: int = 15) -> list:
    """
    Search Adzuna for real job listings matching `query` (a role/keyword string)
    in `country_code` (e.g. "gb", "us", "fr"), optionally narrowed to `where`
    (a city/region). Returns a list of raw listing dicts.
    """
    app_id, app_key = _get_credentials()
    url = f"{BASE_URL}/{country_code}/search/1"
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": results,
        "what": query,
        "content-type": "application/json",
    }
    if where:
        params["where"] = where

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return [{"_error": str(e)}]

    listings = []
    for item in data.get("results", []):
        listings.append({
            "title": item.get("title", "").strip(),
            "company": (item.get("company") or {}).get("display_name", "Unknown"),
            "location": (item.get("location") or {}).get("display_name", ""),
            "description": (item.get("description") or "")[:600],  # trim for token cost
            "apply_link": item.get("redirect_url", "#"),
            "salary_min": item.get("salary_min"),
            "salary_max": item.get("salary_max"),
            "adzuna_id": item.get("id"),
        })
    return listings


def search_multiple_roles(roles: list, country_code: str, where: str = "", per_role: int = 6) -> tuple:
    """
    Runs one Adzuna search per suggested role, merges and de-duplicates results
    by adzuna_id (or title+company if id missing).

    Returns a tuple: (list of unique listings, list of error strings encountered).
    """
    seen = set()
    merged = []
    errors = []
    for role in roles:
        results = search_jobs(role, country_code, where, results=per_role)
        for job in results:
            if "_error" in job:
                errors.append(f"{role}: {job['_error']}")
                continue
            key = job.get("adzuna_id") or f"{job['title']}|||{job['company']}"
            if key not in seen:
                seen.add(key)
                merged.append(job)
    return merged, errors
