#!/usr/bin/env python3
"""Materialise the evidence corpus the synthetic GL benchmark refers to.

``gl_guardian_benchmark_v1.csv`` cites evidence IDs of the form ``ledger:<n>`` and
``policy:<category>``. Without a corpus behind them, citation correctness cannot be
scored and the no-RAG ablation has nothing to remove. This script renders both:

* one ledger document per transaction, restating that row's recorded fields;
* one policy document per risk category, stating the control the category maps to.

Every sentence is a deterministic rendering of data already in the benchmark - the
corpus adds retrievable text, never new facts.

Usage
-----
    python scripts/build_gl_evidence_corpus.py
    python scripts/build_gl_evidence_corpus.py --verify-only
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "datasets" / "gl_guardian_benchmark_v1.csv"
OUTPUT = ROOT / "datasets" / "gl_guardian_benchmark_v1.evidence.json"
CORPUS_VERSION = "gl-evidence-v1"

POLICY_TEXT = {
    "materiality": ("Control policy: postings at or above the 50,000 USD materiality "
                    "threshold require documented secondary review before release."),
    "duplicate": ("Control policy: a posting that matches an earlier entry on vendor, "
                  "amount and period must be investigated as a potential duplicate "
                  "payment before settlement."),
    "document_gap": ("Control policy: every posting requires a purchase-order reference "
                     "and a complete supporting-document set; either being absent is a "
                     "control exception."),
    "segregation_of_duties": ("Control policy: the individual who posts an entry may not "
                              "also approve it. A shared identifier in both fields is a "
                              "segregation-of-duties breach."),
    "related_party": ("Control policy: postings to counterparties flagged as related "
                      "parties require disclosure and independent approval."),
    "normal": ("Control policy: postings that clear the materiality, duplication, "
               "documentation, segregation and related-party controls are released "
               "without further examination."),
    "borderline": ("Control policy: postings close to a control threshold are routed to "
                   "auditor judgement rather than decided by the threshold alone."),
    "hard_negative": ("Control policy: a posting may resemble a flagged pattern while "
                      "still satisfying every control. Resemblance alone is not a finding."),
    "hard_positive": ("Control policy: a posting may satisfy each control individually "
                      "while the combination of weak indicators still warrants escalation."),
}


def render(rows: list[dict[str, str]]) -> dict[str, str]:
    documents: dict[str, str] = {}
    for row in rows:
        for evidence_id in row["evidence_ids"].split(";"):
            if not evidence_id:
                continue
            kind, _, value = evidence_id.partition(":")
            if kind == "ledger":
                documents[evidence_id] = (
                    f"Ledger record {evidence_id} for transaction {row['transaction_id']}: "
                    f"{row['amount_usd']} {row['currency']} paid to vendor "
                    f"{row['vendor_id']} by {row['payment_method']}. "
                    f"Purchase order: {row['po_number'] or 'none recorded'}. "
                    f"Supporting documents: {row['document_status']}. "
                    f"Posted by {row['posted_by']}, approved by {row['approved_by']}. "
                    f"Related-party indicator: "
                    f"{'yes' if row['related_party_flag'] == 'Y' else 'no'}. "
                    + (f"Flagged as a duplicate of {row['duplicate_of']}."
                       if row["duplicate_of"] else "No duplicate reference recorded.")
                )
            elif kind == "policy":
                documents.setdefault(
                    evidence_id,
                    POLICY_TEXT.get(value, f"Control policy reference {value}: "
                                           f"no policy text is on file for this category."))
    return documents


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    if not SOURCE.exists():
        print(f"missing {SOURCE}; run scripts/generate_benchmark_dataset.py first")
        return 1
    with SOURCE.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    documents = render(rows)
    payload = json.dumps({"dataset_version": CORPUS_VERSION, "documents": documents},
                         indent=2, sort_keys=True) + "\n"

    referenced = set()
    for row in rows:
        referenced.update(part for part in row["evidence_ids"].split(";") if part)
    dangling = sorted(referenced - set(documents))
    if dangling:
        print(f"FAIL: {len(dangling)} evidence IDs have no document, e.g. {dangling[:5]}")
        return 1

    if args.verify_only:
        if not OUTPUT.exists():
            print("FAIL: corpus has not been built yet")
            return 1
        if OUTPUT.read_text(encoding="utf-8") != payload:
            print("FAIL: committed corpus differs from a fresh build")
            return 1
        print(f"OK: {len(documents)} documents, every referenced ID resolves")
        return 0

    OUTPUT.write_text(payload, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}: {len(documents)} documents "
          f"covering {len(referenced)} referenced IDs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
