"""One-off probe for the Duffel flight-fares and Duffel Stays providers.

Confirms the request/response shapes with your key. Test keys return synthetic
offers (usually GBP), not real market prices.

Usage:
    # from Backend/ with your key exported (or set in .env)
    DUFFEL_API_KEY=duffel_test_xxx python scripts/probe_duffel.py flights LHR JFK 2026-09-01
    DUFFEL_API_KEY=duffel_test_xxx python scripts/probe_duffel.py stays 51.5071 -0.1416 2026-09-01 2026-09-03
"""

from __future__ import annotations

import json
import os
import statistics
import sys

import requests

BASE = os.environ.get("DUFFEL_API_BASE_URL", "https://api.duffel.com").rstrip("/")
KEY = os.environ.get("DUFFEL_API_KEY", "")
VERSION = os.environ.get("DUFFEL_API_VERSION", "v2")


def headers() -> dict:
    return {
        "Authorization": f"Bearer {KEY}",
        "Duffel-Version": VERSION,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def flights(origin: str, destination: str, date: str) -> None:
    url = f"{BASE}/air/offer_requests"
    payload = {
        "data": {
            "slices": [{"origin": origin, "destination": destination, "departure_date": date}],
            "passengers": [{"type": "adult"}],
            "cabin_class": "economy",
        }
    }
    r = requests.post(url, params={"return_offers": "true"}, json=payload, headers=headers(), timeout=30)
    print("Status:", r.status_code)
    data = r.json()
    offers = (data.get("data") or {}).get("offers") or []
    amounts = [float(o["total_amount"]) for o in offers if o.get("total_amount")]
    if amounts:
        cur = offers[0].get("total_currency")
        print(f"{len(amounts)} offers | median {statistics.median(amounts):,.2f} {cur} | "
              f"live_mode={ (data.get('data') or {}).get('live_mode') }")
    else:
        print("No offers:", json.dumps(data, indent=2)[:1500])


def stays(lat: str, lon: str, check_in: str, check_out: str) -> None:
    url = f"{BASE}/stays/search"
    payload = {
        "data": {
            "rooms": 1,
            "location": {"radius": 5, "geographic_coordinates": {"longitude": float(lon), "latitude": float(lat)}},
            "guests": [{"type": "adult"}],
            "check_in_date": check_in,
            "check_out_date": check_out,
        }
    }
    r = requests.post(url, json=payload, headers=headers(), timeout=30)
    print("Status:", r.status_code)
    data = r.json()
    results = (data.get("data") or {}).get("results") or []
    amounts = [float(x["cheapest_rate_total_amount"]) for x in results if x.get("cheapest_rate_total_amount")]
    if amounts:
        cur = results[0].get("cheapest_rate_currency")
        print(f"{len(amounts)} properties | median stay total {statistics.median(amounts):,.2f} {cur}")
    else:
        print("No results:", json.dumps(data, indent=2)[:1500])


def main() -> None:
    if not KEY:
        sys.exit("Set DUFFEL_API_KEY (export it or put it in .env).")
    mode = sys.argv[1] if len(sys.argv) > 1 else "flights"
    if mode == "flights":
        flights(*(sys.argv[2:5] or ["LHR", "JFK", "2026-09-01"]))
    elif mode == "stays":
        stays(*(sys.argv[2:6] or ["51.5071", "-0.1416", "2026-09-01", "2026-09-03"]))
    else:
        sys.exit("First arg must be 'flights' or 'stays'.")


if __name__ == "__main__":
    main()
