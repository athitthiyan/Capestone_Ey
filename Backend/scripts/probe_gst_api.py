"""One-off probe for the GSTINCheck GST validity provider.

Confirms the response shape and that a GSTIN resolves. This is an identity check
(Active = VERIFIED, cancelled/not-found = FLAGGED); it returns no amount.

Usage:
    # from Backend/ with your key exported (or set in .env)
    GST_VERIFICATION_PROVIDER_API_KEY=xxxx python scripts/probe_gst_api.py 29AAACWXXXXX1ZV

Each call uses one credit. If "flag" is false the GSTIN is invalid/not found.
"""

from __future__ import annotations

import json
import os
import sys

import requests

BASE_URL = os.environ.get("GST_VERIFICATION_BASE_URL", "https://sheet.gstincheck.co.in").rstrip("/")
API_KEY = os.environ.get("GST_VERIFICATION_PROVIDER_API_KEY", "")
PATH = os.environ.get("GST_VERIFICATION_CHECK_PATH", "/check").strip("/")


def main() -> None:
    if not API_KEY:
        sys.exit("Set GST_VERIFICATION_PROVIDER_API_KEY (export it or put it in .env).")
    if len(sys.argv) < 2:
        sys.exit("Pass a GSTIN, e.g. python scripts/probe_gst_api.py 29AAACWXXXXX1ZV")

    gstin = sys.argv[1].strip().upper()
    url = f"{BASE_URL}/{PATH}/{API_KEY}/{gstin}"
    print(f"GET {BASE_URL}/{PATH}/<key>/{gstin}\n")
    resp = requests.get(url, headers={"Accept": "application/json"}, timeout=10)
    print(f"Status: {resp.status_code}")
    try:
        data = resp.json()
    except ValueError:
        print("Non-JSON response:\n", resp.text[:2000])
        return

    flag = data.get("flag") if isinstance(data, dict) else None
    details = (data.get("data") if isinstance(data, dict) else None) or {}
    if flag is False or not details:
        print("\n--- FLAGGED (not found/invalid) ---", data.get("message", ""))
    else:
        sts = details.get("sts") or details.get("status")
        print(f"\n--- status: {sts} | legal: {details.get('lgnm')} | trade: {details.get('tradeNam')} ---")
    print(json.dumps(data, indent=2, ensure_ascii=False)[:3000])


if __name__ == "__main__":
    main()
