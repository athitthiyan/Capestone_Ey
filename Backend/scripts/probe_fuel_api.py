"""One-off probe for the IndianAPI fuel provider.

Confirms the live response shape so the evidence-verification adapter parses it
correctly. Run once after setting FUEL_PRICE_PROVIDER_API_KEY.

Usage:
    # from Backend/ with your key exported (or set in .env)
    FUEL_PRICE_PROVIDER_API_KEY=xxxx python scripts/probe_fuel_api.py "Chennai" petrol

It prints the raw JSON and the price the adapter's parser extracts. If the price
comes back as None, copy the printed JSON here and I'll adjust the parser keys.
"""

from __future__ import annotations

import json
import os
import sys

import requests

BASE_URL = os.environ.get("FUEL_PRICE_PROVIDER_URL", "https://fuel.indianapi.in").rstrip("/")
API_KEY = os.environ.get("FUEL_PRICE_PROVIDER_API_KEY", "")
HEADER = os.environ.get("FUEL_PRICE_PROVIDER_HEADER", "x-api-key")
PATH = os.environ.get("FUEL_PRICE_LIVE_PATH", "/live_fuel_price")


def main() -> None:
    if not API_KEY:
        sys.exit("Set FUEL_PRICE_PROVIDER_API_KEY (export it or put it in .env).")

    city = sys.argv[1] if len(sys.argv) > 1 else "Chennai"
    fuel_type = (sys.argv[2] if len(sys.argv) > 2 else "petrol").lower()

    url = f"{BASE_URL}{PATH}"
    print(f"GET {url}?city={city}  (header {HEADER})\n")
    resp = requests.get(
        url,
        params={"city": city},
        headers={"Accept": "application/json", HEADER: API_KEY},
        timeout=10,
    )
    print(f"Status: {resp.status_code}")
    try:
        data = resp.json()
    except ValueError:
        print("Non-JSON response:\n", resp.text[:2000])
        return

    print("\n--- RAW JSON ---")
    print(json.dumps(data, indent=2, ensure_ascii=False)[:4000])

    # Reuse the adapter's parser so this matches production behaviour exactly.
    sys.path.insert(0, os.path.abspath("."))
    try:
        from app.evidence_verification.providers import _find_fuel_price

        price = _find_fuel_price(data, fuel_type)
        print(f"\n--- PARSED {fuel_type} price/L: {price} ---")
        if price is None:
            print("Parser found nothing — paste the RAW JSON above so the keys can be tuned.")
    except Exception as exc:  # noqa: BLE001
        print(f"\n(Could not import adapter parser: {exc})")


if __name__ == "__main__":
    main()
