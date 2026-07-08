"""One-off probe for the Aviationstack flight route-existence validator.

Confirms the /routes response shape and that a route resolves. Aviationstack
validates that a route EXISTS in airline schedules; it does NOT return fares.

Usage:
    # from Backend/ with your key exported (or set in .env)
    FLIGHT_VALIDATION_API_KEY=xxxx python scripts/probe_flight_api.py MAA DEL

If "data" comes back with entries, the route is real (VERIFIED). Empty data
means the route was not found (FLAGGED). An "error" payload means the key/quota
is the problem (API_UNAVAILABLE).
"""

from __future__ import annotations

import json
import os
import sys

import requests

BASE_URL = os.environ.get(
    "FLIGHT_VALIDATION_PROVIDER_URL", "https://api.aviationstack.com/v1"
).rstrip("/")
API_KEY = os.environ.get("FLIGHT_VALIDATION_API_KEY", "")
PATH = os.environ.get("FLIGHT_VALIDATION_ROUTES_PATH", "/routes")


def main() -> None:
    if not API_KEY:
        sys.exit("Set FLIGHT_VALIDATION_API_KEY (export it or put it in .env).")

    dep = (sys.argv[1] if len(sys.argv) > 1 else "MAA").upper()
    arr = (sys.argv[2] if len(sys.argv) > 2 else "DEL").upper()

    url = f"{BASE_URL}{PATH}"
    print(f"GET {url}?dep_iata={dep}&arr_iata={arr}\n")
    resp = requests.get(
        url,
        params={"access_key": API_KEY, "dep_iata": dep, "arr_iata": arr, "limit": 20},
        headers={"Accept": "application/json"},
        timeout=10,
    )
    print(f"Status: {resp.status_code}")
    try:
        data = resp.json()
    except ValueError:
        print("Non-JSON response:\n", resp.text[:2000])
        return

    if isinstance(data, dict) and data.get("error"):
        print("API error (check key/quota):", json.dumps(data["error"], indent=2))
        return

    results = (data.get("data") if isinstance(data, dict) else None) or []
    verdict = "VERIFIED (route exists)" if results else "FLAGGED (route not found)"
    print(f"\n--- {verdict}: {len(results)} scheduled route(s) ---")
    print(json.dumps(data, indent=2, ensure_ascii=False)[:3000])


if __name__ == "__main__":
    main()
