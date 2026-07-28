"""Generate the privacy-safe GL Guardian synthetic benchmark."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from collections import Counter
from pathlib import Path

SEED = 20260728
VERSION = "1.0.0"
CATEGORIES = (
    "normal",
    "materiality",
    "related_party",
    "document_gap",
    "segregation_of_duties",
    "duplicate",
    "borderline",
    "hard_negative",
    "hard_positive",
)


def _split(transaction_id: str) -> str:
    value = int.from_bytes(hashlib.sha256(f"{SEED}:{transaction_id}".encode()).digest()[:8], "big")
    return "evaluation" if value % 5 == 0 else "development"


def generate_rows(size: int = 600, seed: int = SEED) -> list[dict[str, object]]:
    if size < 500 or size % 2:
        raise ValueError("size must be an even integer of at least 500")
    rng = random.Random(seed)
    rows: list[dict[str, object]] = []
    positive_categories = [
        "materiality", "related_party", "document_gap", "segregation_of_duties",
        "duplicate", "borderline", "hard_positive",
    ]
    for index in range(size):
        label = 1 if index % 2 else 0
        if label:
            category = positive_categories[(index // 2) % len(positive_categories)]
        else:
            category = "hard_negative" if index % 4 == 0 else "normal"
        amount = round(rng.uniform(100, 45_000), 2)
        document_status = "complete"
        related = "N"
        posted_by = f"user{index % 19:02d}"
        approved_by = f"approver{index % 13:02d}"
        payment_method = rng.choice(["ACH", "Wire", "Corporate card"])
        po_number = f"PO-{index + 1:06d}"
        duplicate_of = ""
        difficulty = "standard"
        if category == "materiality":
            amount = round(rng.uniform(55_000, 200_000), 2)
        elif category == "related_party":
            related = "Y"
        elif category == "document_gap":
            document_status, po_number = "missing_invoice", ""
        elif category == "segregation_of_duties":
            approved_by = posted_by
        elif category == "duplicate":
            duplicate_of = f"GLB-{max(1, index):06d}"
        elif category == "borderline":
            amount, difficulty = round(rng.uniform(47_500, 52_500), 2), "borderline"
        elif category == "hard_positive":
            amount, difficulty, document_status = round(rng.uniform(200, 2_000), 2), "hard", "altered"
        elif category == "hard_negative":
            amount, difficulty, payment_method = round(rng.uniform(60_000, 180_000), 2), "hard", "Manual journal"
        row = {
            "transaction_id": f"GLB-{index + 1:06d}",
            "vendor_id": f"SYN-V-{index % 73:03d}",
            "amount_usd": f"{amount:.2f}",
            "currency": "USD",
            "document_status": document_status,
            "po_number": po_number,
            "payment_method": payment_method,
            "posted_by": posted_by,
            "approved_by": approved_by,
            "related_party_flag": related,
            "duplicate_of": duplicate_of,
            "risk_label": label,
            "risk_category": category,
            "difficulty": difficulty,
            "evidence_ids": f"ledger:{index + 1};policy:{category}",
            "split": _split(f"GLB-{index + 1:06d}"),
            "generator_version": VERSION,
        }
        rows.append(row)
    rng.shuffle(rows)
    return rows


def write_dataset(output: Path, size: int = 600, seed: int = SEED) -> dict[str, object]:
    rows = generate_rows(size=size, seed=seed)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    manifest = {
        "dataset_version": VERSION,
        "seed": seed,
        "rows": len(rows),
        "sha256": digest,
        "class_distribution": dict(Counter(str(row["risk_label"]) for row in rows)),
        "category_distribution": dict(Counter(str(row["risk_category"]) for row in rows)),
        "split_distribution": dict(Counter(str(row["split"]) for row in rows)),
    }
    output.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, default=600)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--output", type=Path, default=Path("datasets/gl_guardian_benchmark_v1.csv"))
    args = parser.parse_args()
    print(json.dumps(write_dataset(args.output, args.size, args.seed), indent=2))


if __name__ == "__main__":
    main()
