#!/usr/bin/env python3
"""Seed demo employee transactions through the public API.

Registers a few demo employee users (idempotent) and creates a realistic
spread of transactions for each - types, statuses, currencies, and dates
over the last 60 days - so the Employee Transactions view has data without
manual entry.

Usage:
    python scripts/seed_employee_transactions.py \
        --base-url http://localhost:8000 \
        --username <elevated_user> --password <password>

Notes:
    - The creating user should be elevated (partner/admin) so transactions
      can be created for other employees via employee_id.
    - Auth routes are rate-limited (register: 5/window, token: 10/window);
      the script stays under those limits and sleeps between calls.
"""
from __future__ import annotations

import argparse
import random
import sys
import time
from datetime import datetime, timedelta

import requests

DEMO_EMPLOYEES = [
    {"username": "arjun.mehta", "email": "arjun.mehta@acme-corp.com", "password": "DemoPass123!"},
    {"username": "maria.lopez", "email": "maria.lopez@acme-corp.com", "password": "DemoPass123!"},
    {"username": "david.chen", "email": "david.chen@acme-corp.com", "password": "DemoPass123!"},
    {"username": "sara.ali", "email": "sara.ali@acme-corp.com", "password": "DemoPass123!"},
]

TXN_TEMPLATES = [
    ("reimbursement", "Travel reimbursement - client visit", "USD", (120, 1800), "completed"),
    ("reimbursement", "Meal expense reimbursement", "USD", (18, 240), "completed"),
    ("reimbursement", "Hotel stay reimbursement", "USD", (300, 1400), "pending"),
    ("payroll", "Monthly salary", "USD", (4200, 9800), "completed"),
    ("bonus", "Quarterly performance bonus", "USD", (500, 5000), "completed"),
    ("debit", "Corporate card - software purchase", "USD", (49, 900), "completed"),
    ("debit", "Corporate card - office equipment", "USD", (150, 2200), "pending"),
    ("deduction", "Insurance premium deduction", "USD", (85, 420), "completed"),
    ("adjustment", "Expense report correction", "USD", (25, 600), "completed"),
    ("reimbursement", "Fuel reimbursement - fleet travel", "INR", (900, 8000), "pending"),
    ("debit", "Training course fee", "EUR", (200, 1500), "completed"),
    ("credit", "Refund - cancelled booking", "USD", (60, 800), "failed"),
]


def login(base: str, username: str, password: str) -> str:
    r = requests.post(f"{base}/api/v1/auth/token",
                      data={"username": username, "password": password}, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--username", required=True, help="elevated user (partner/admin)")
    ap.add_argument("--password", required=True)
    ap.add_argument("--per-employee", type=int, default=8)
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()
    base = args.base_url.rstrip("/")
    rng = random.Random(args.seed)

    admin_token = login(base, args.username, args.password)
    admin_hdr = {"Authorization": f"Bearer {admin_token}"}

    # 1) Ensure demo employees exist and resolve their user ids.
    employee_ids: dict[str, str] = {}
    for emp in DEMO_EMPLOYEES:
        r = requests.post(f"{base}/api/v1/auth/register",
                          json={**emp, "role": "analyst"}, timeout=30)
        if r.status_code == 201:
            employee_ids[emp["username"]] = r.json()["id"]
            print(f"registered {emp['username']}")
        elif r.status_code == 409:
            tok = login(base, emp["username"], emp["password"])
            me = requests.get(f"{base}/api/v1/auth/me",
                              headers={"Authorization": f"Bearer {tok}"}, timeout=30)
            me.raise_for_status()
            employee_ids[emp["username"]] = me.json()["id"]
            print(f"exists     {emp['username']}")
        else:
            print(f"WARN: register {emp['username']} -> {r.status_code} {r.text[:120]}")
        time.sleep(1.5)  # stay friendly with the rate limiter

    if not employee_ids:
        print("No employees resolved; aborting.")
        return 1

    # 2) Create transactions spread over the last 60 days.
    created = 0
    for username, emp_id in employee_ids.items():
        picks = rng.sample(TXN_TEMPLATES, k=min(args.per_employee, len(TXN_TEMPLATES)))
        for i, (ttype, desc, ccy, (lo, hi), status) in enumerate(picks):
            when = datetime.utcnow() - timedelta(days=rng.randint(0, 60),
                                                 hours=rng.randint(0, 12))
            payload = {
                "employee_id": emp_id,
                "transaction_type": ttype,
                "amount": round(rng.uniform(lo, hi), 2),
                "currency": ccy,
                "status": status,
                "description": desc,
                "reference_id": f"REF-{username.split('.')[0].upper()}-{i+1:03d}",
                "transaction_date": when.isoformat(),
            }
            r = requests.post(f"{base}/api/v1/employee-transactions",
                              json=payload, headers=admin_hdr, timeout=30)
            if r.status_code == 201:
                created += 1
            else:
                print(f"WARN: txn for {username} -> {r.status_code} {r.text[:120]}")
            time.sleep(0.2)

    print(f"done: {created} transactions across {len(employee_ids)} employees")
    return 0


if __name__ == "__main__":
    sys.exit(main())
