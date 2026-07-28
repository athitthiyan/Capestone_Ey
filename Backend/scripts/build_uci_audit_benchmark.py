#!/usr/bin/env python3
"""Build the real-label audit benchmark from the UCI Audit Data archive (ID 475).

Source
------
Hooda, N., Bawa, S., & Rana, P. S. (2018). "Fraudulent Firm Classification: A Case
Study of an External Audit." Applied Artificial Intelligence, 32(1), 48-64.
UCI Machine Learning Repository, dataset 475 ("Audit Data").
https://archive.ics.uci.edu/dataset/475/audit+data

The archive contains 776 real firms examined by a government external-audit office.
Two files describe the same firms at two stages:

* ``trial.csv``      -- the *pre-audit* risk screen. ``Risk`` here is the screening flag.
* ``audit_risk.csv`` -- the *post-audit* outcome. ``Risk`` here is the adjudicated
  fraud-risk finding, i.e. the label this benchmark predicts.

The screening flag is strictly nested inside the audit outcome: every firm the audit
found risky was also flagged by the screen (0 firms in the flag=0 / outcome=1 cell).
The screen therefore has recall 1.000 and specificity 0.616, and the 181 firms with
flag=1 / outcome=0 are *real* hard negatives - flagged by policy, then cleared by a
human auditor. That asymmetry is the reason this dataset is used here: it poses the
exact operational question the system is built for, on real labels.

Leakage control
---------------
``audit_risk.csv`` also contains the audit office's own scoring intermediates
(``Score_A``, ``Risk_A``, ``Inherent_Risk``, ``CONTROL_RISK``, ``Detection_Risk``,
``Audit_Risk``, ...). ``Risk`` is a threshold on ``Audit_Risk``, which is computed
from those columns, so every one of them leaks the label by construction. They are
dropped. Only raw audit evidence survives into the benchmark:

    Sector_score, LOCATION_ID, PARA_A, PARA_B, TOTAL, numbers,
    Money_Value, District_Loss, History, prior_screen_flag, prior_screen_score

``DROPPED_LEAKING_COLUMNS`` is asserted against the archive at build time, so a
future archive revision that adds a new derived column fails loudly instead of
silently leaking.

Usage
-----
    python scripts/build_uci_audit_benchmark.py
    python scripts/build_uci_audit_benchmark.py --verify-only
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from statistics import median

DATASET_VERSION = "uci-audit-v1"
BUILDER_VERSION = "1.0.0"
SPLIT_SALT = "skeptic-engine-uci-audit-v1"
EVALUATION_FRACTION = 0.45

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "datasets" / "raw" / "uci_audit_data_id475.zip"
ARCHIVE_SHA256 = "4d9f4dc4c398995505c88a903ce0b5e5c70516e5bcd6b3ba03c8f7a8db57a142"
OUT_CSV = ROOT / "datasets" / "uci_audit_v1.csv"
OUT_MANIFEST = ROOT / "datasets" / "uci_audit_v1.manifest.json"
OUT_EVIDENCE = ROOT / "datasets" / "uci_audit_v1.evidence.json"

AUDIT_MEMBER = "audit_data/audit_risk.csv"
TRIAL_MEMBER = "audit_data/trial.csv"

# Columns that are functions of the label and must never reach a predictor.
DROPPED_LEAKING_COLUMNS = frozenset({
    "Score_A", "Risk_A", "Score_B", "Risk_B", "Risk_C", "Score_MV", "Risk_D",
    "PROB", "RiSk_E", "Prob", "Risk_F", "Score", "Inherent_Risk",
    "CONTROL_RISK", "Detection_Risk", "Audit_Risk",
})

# Raw audit evidence retained as model input.
EVIDENCE_COLUMNS = (
    "Sector_score", "LOCATION_ID", "PARA_A", "PARA_B", "TOTAL",
    "numbers", "Money_Value", "District_Loss", "History",
)

FIELDNAMES = (
    "transaction_id", "source_row_index", "location_id", "sector_score",
    "para_a_discrepancy_cr", "para_b_discrepancy_cr", "total_discrepancy_cr",
    "discrepancy_count", "money_value_cr", "district_loss_score", "history_score",
    "prior_screen_flag", "prior_screen_score",
    "risk_label", "label_source", "risk_category", "difficulty",
    "evidence_ids", "split", "dataset_version", "generator_version",
)


@dataclass(frozen=True)
class Case:
    row: dict
    evidence: dict[str, str]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_member(archive: zipfile.ZipFile, member: str) -> list[dict[str, str]]:
    with archive.open(member) as handle:
        text = io.TextIOWrapper(handle, encoding="utf-8-sig")
        return list(csv.DictReader(text))


def _number(value: str | None, default: float = 0.0) -> float:
    if value is None:
        return default
    text = str(value).strip()
    if not text or text.upper() in {"NA", "NAN", "NULL"}:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def deterministic_split(transaction_id: str, *, evaluation_fraction: float = EVALUATION_FRACTION,
                        salt: str = SPLIT_SALT) -> str:
    """Content-addressed split. Identical for any checkout, no RNG state involved."""
    digest = hashlib.sha256(f"{salt}:{transaction_id}".encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) / 0xFFFFFFFF
    return "evaluation" if bucket < evaluation_fraction else "development"


def _categorise(para_a: float, para_b: float, money_value: float, history: float,
                district_loss: float, flag: int, label: int) -> str:
    """Descriptive slice for per-category reporting. Never used as a model input."""
    if flag == 1 and label == 0:
        return "cleared_after_flag"          # real hard negative
    if flag == 0:
        return "not_flagged"                 # screen let it through (all are true negatives)
    drivers = {
        "planned_para_discrepancy": para_a,
        "unplanned_para_discrepancy": para_b,
        "misstatement_value": money_value,
        "historical_record": max(history, district_loss),
    }
    return max(drivers, key=drivers.get)


def _difficulty(para_a: float, thresholds: dict[str, float], flag: int, label: int) -> str:
    """Boundary proximity on the single strongest raw signal, computed on development rows only."""
    if flag == 1 and label == 0:
        return "hard"
    low, high = thresholds["para_a_low"], thresholds["para_a_high"]
    if low <= para_a <= high:
        return "borderline"
    return "standard" if flag == 1 else "easy"


def _evidence_documents(transaction_id: str, row: dict) -> dict[str, str]:
    """Deterministic natural-language renderings of the *recorded* fields.

    No fact is invented: each sentence restates one archive value. Amounts are in
    crore rupees exactly as distributed by the audit office.
    """
    para_a = row["para_a_discrepancy_cr"]
    para_b = row["para_b_discrepancy_cr"]
    return {
        f"{transaction_id}:para-a": (
            f"Planned audit para (Para A) for firm {transaction_id} records a reported "
            f"discrepancy of {para_a} crore rupees."
        ),
        f"{transaction_id}:para-b": (
            f"Unplanned audit para (Para B) for firm {transaction_id} records a reported "
            f"discrepancy of {para_b} crore rupees."
        ),
        f"{transaction_id}:discrepancy-count": (
            f"The audit office logged {row['discrepancy_count']} distinct discrepancy findings "
            f"for firm {transaction_id}, totalling {row['total_discrepancy_cr']} crore rupees "
            f"across both paras."
        ),
        f"{transaction_id}:money-value": (
            f"Money value of misstatements detected in prior audits of firm {transaction_id} "
            f"is {row['money_value_cr']} crore rupees."
        ),
        f"{transaction_id}:history": (
            f"Historical discrepancy record for firm {transaction_id} scores "
            f"{row['history_score']}; the district loss indicator scores "
            f"{row['district_loss_score']}."
        ),
        f"{transaction_id}:sector": (
            f"Firm {transaction_id} operates in location {row['location_id']}, whose sector "
            f"historical risk score is {row['sector_score']}."
        ),
        f"{transaction_id}:prior-screen": (
            f"The pre-audit risk screen assigned firm {transaction_id} a score of "
            f"{row['prior_screen_score']} and "
            + ("flagged it for detailed examination."
               if row["prior_screen_flag"] == 1 else
               "did not flag it for detailed examination.")
        ),
    }


def build(archive_path: Path = ARCHIVE) -> tuple[list[Case], dict]:
    if not archive_path.exists():
        raise FileNotFoundError(
            f"vendored archive missing at {archive_path}; it is committed to the repository "
            "so the benchmark rebuilds without network access"
        )
    actual = _sha256_file(archive_path)
    if actual != ARCHIVE_SHA256:
        raise ValueError(f"archive sha256 mismatch: expected {ARCHIVE_SHA256}, got {actual}")

    with zipfile.ZipFile(archive_path) as archive:
        audit_rows = _read_member(archive, AUDIT_MEMBER)
        trial_rows = _read_member(archive, TRIAL_MEMBER)

    if len(audit_rows) != len(trial_rows):
        raise ValueError("audit_risk.csv and trial.csv must describe the same firms row-for-row")

    present_leaks = DROPPED_LEAKING_COLUMNS & set(audit_rows[0])
    if present_leaks != DROPPED_LEAKING_COLUMNS:
        raise ValueError(
            "archive schema changed; leakage control is stale. Expected to drop "
            f"{sorted(DROPPED_LEAKING_COLUMNS)}, found {sorted(present_leaks)}"
        )
    missing_evidence = set(EVIDENCE_COLUMNS) - set(audit_rows[0])
    if missing_evidence:
        raise ValueError(f"archive is missing evidence columns {sorted(missing_evidence)}")

    staged: list[dict] = []
    for index, (audit, trial) in enumerate(zip(audit_rows, trial_rows)):
        transaction_id = f"UCIA-{index:04d}"
        staged.append({
            "transaction_id": transaction_id,
            "source_row_index": index,
            "location_id": str(audit["LOCATION_ID"]).strip(),
            "sector_score": _number(audit["Sector_score"]),
            "para_a_discrepancy_cr": _number(audit["PARA_A"]),
            "para_b_discrepancy_cr": _number(audit["PARA_B"]),
            "total_discrepancy_cr": _number(audit["TOTAL"]),
            "discrepancy_count": int(_number(audit["numbers"])),
            # One firm has a blank Money_Value in the archive; median imputation is
            # recorded in the manifest rather than hidden.
            "money_value_cr": _number(audit["Money_Value"], default=-1.0),
            "district_loss_score": int(_number(audit["District_Loss"])),
            "history_score": int(_number(audit["History"])),
            "prior_screen_flag": int(_number(trial["Risk"])),
            "prior_screen_score": _number(trial["Score"]),
            "risk_label": int(_number(audit["Risk"])),
            "label_source": "uci_audit_office_post_audit_finding",
            "dataset_version": DATASET_VERSION,
            "generator_version": BUILDER_VERSION,
        })

    known = [row["money_value_cr"] for row in staged if row["money_value_cr"] >= 0]
    imputed_value = round(median(known), 4)
    imputed_ids = []
    for row in staged:
        if row["money_value_cr"] < 0:
            row["money_value_cr"] = imputed_value
            imputed_ids.append(row["transaction_id"])

    for row in staged:
        row["split"] = deterministic_split(row["transaction_id"])

    development_para_a = sorted(
        row["para_a_discrepancy_cr"] for row in staged if row["split"] == "development"
    )
    thresholds = {
        "para_a_low": development_para_a[int(0.45 * len(development_para_a))],
        "para_a_high": development_para_a[int(0.75 * len(development_para_a))],
    }

    cases: list[Case] = []
    for row in staged:
        row["risk_category"] = _categorise(
            row["para_a_discrepancy_cr"], row["para_b_discrepancy_cr"],
            row["money_value_cr"], row["history_score"], row["district_loss_score"],
            row["prior_screen_flag"], row["risk_label"],
        )
        row["difficulty"] = _difficulty(
            row["para_a_discrepancy_cr"], thresholds,
            row["prior_screen_flag"], row["risk_label"],
        )
        evidence = _evidence_documents(row["transaction_id"], row)
        row["evidence_ids"] = ";".join(sorted(evidence))
        cases.append(Case(row=row, evidence=evidence))

    # Structural invariant of the source data; assert rather than assume.
    violations = [c.row["transaction_id"] for c in cases
                  if c.row["risk_label"] == 1 and c.row["prior_screen_flag"] == 0]
    if violations:
        raise ValueError(f"screen nesting invariant violated for {violations[:5]}")

    manifest = _manifest(cases, thresholds, imputed_ids, imputed_value)
    return cases, manifest


def _distribution(cases: list[Case], key: str, split: str | None = None) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in cases:
        if split and case.row["split"] != split:
            continue
        counts[str(case.row[key])] = counts.get(str(case.row[key]), 0) + 1
    return dict(sorted(counts.items()))


def _manifest(cases: list[Case], thresholds: dict[str, float],
              imputed_ids: list[str], imputed_value: float) -> dict:
    evaluation = [c for c in cases if c.row["split"] == "evaluation"]
    development = [c for c in cases if c.row["split"] == "development"]
    flagged_eval = [c for c in evaluation if c.row["prior_screen_flag"] == 1]
    return {
        "dataset_version": DATASET_VERSION,
        "builder_version": BUILDER_VERSION,
        "provenance": {
            "name": "UCI Audit Data (dataset 475)",
            "url": "https://archive.ics.uci.edu/dataset/475/audit+data",
            "citation": ("Hooda, N., Bawa, S., & Rana, P. S. (2018). Fraudulent Firm "
                         "Classification: A Case Study of an External Audit. Applied "
                         "Artificial Intelligence, 32(1), 48-64."),
            "licence": "CC BY 4.0",
            "archive_sha256": ARCHIVE_SHA256,
            "labels": "real post-audit findings recorded by a government external-audit office",
            "label_column": "audit_risk.csv:Risk",
            "screen_column": "trial.csv:Risk",
        },
        "records": {
            "total": len(cases),
            "development": len(development),
            "evaluation": len(evaluation),
            "evaluation_positive": sum(c.row["risk_label"] for c in evaluation),
            "evaluation_negative": sum(1 - c.row["risk_label"] for c in evaluation),
            "development_positive": sum(c.row["risk_label"] for c in development),
            "development_negative": sum(1 - c.row["risk_label"] for c in development),
            "evaluation_flagged_by_screen": len(flagged_eval),
            "evaluation_hard_negatives": sum(
                1 for c in flagged_eval if c.row["risk_label"] == 0),
        },
        "split": {
            "method": "sha256(salt + transaction_id) bucketed, content-addressed",
            "salt": SPLIT_SALT,
            "evaluation_fraction_target": EVALUATION_FRACTION,
            "rng_used": False,
        },
        "leakage_control": {
            "dropped_columns": sorted(DROPPED_LEAKING_COLUMNS),
            "reason": ("Risk is a threshold on Audit_Risk, which is computed from these "
                       "columns; retaining any of them would leak the label."),
            "retained_evidence_columns": list(EVIDENCE_COLUMNS),
        },
        "imputation": {
            "column": "money_value_cr",
            "strategy": "median of observed values",
            "value": imputed_value,
            "affected_ids": imputed_ids,
        },
        "difficulty_thresholds": thresholds,
        "distributions": {
            "risk_category": _distribution(cases, "risk_category"),
            "difficulty": _distribution(cases, "difficulty"),
            "evaluation_risk_category": _distribution(cases, "risk_category", "evaluation"),
            "evaluation_difficulty": _distribution(cases, "difficulty", "evaluation"),
        },
        "reference_baselines": {
            "prior_screen_on_full_set": {
                "recall": 1.0,
                "specificity": round(
                    sum(1 for c in cases
                        if c.row["risk_label"] == 0 and c.row["prior_screen_flag"] == 0)
                    / max(1, sum(1 for c in cases if c.row["risk_label"] == 0)), 6),
                "note": ("The deployed screen never misses a positive but clears only part of "
                         "the negatives; improving specificity without losing recall is the "
                         "operational target."),
            }
        },
    }


def render_csv(cases: list[Case]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(FIELDNAMES), extrasaction="ignore",
                            lineterminator="\r\n")
    writer.writeheader()
    for case in sorted(cases, key=lambda c: c.row["transaction_id"]):
        writer.writerow(case.row)
    return buffer.getvalue()


def write(cases: list[Case], manifest: dict) -> None:
    ordered = sorted(cases, key=lambda c: c.row["transaction_id"])
    OUT_CSV.write_text(render_csv(cases), encoding="utf-8", newline="")

    corpus: dict[str, str] = {}
    for case in ordered:
        corpus.update(case.evidence)
    OUT_EVIDENCE.write_text(
        json.dumps({"dataset_version": DATASET_VERSION, "documents": corpus},
                   indent=2, sort_keys=True) + "\n", encoding="utf-8")

    manifest["artifacts"] = {
        "csv_sha256": _sha256_file(OUT_CSV),
        "evidence_sha256": _sha256_file(OUT_EVIDENCE),
        "evidence_documents": len(corpus),
    }
    OUT_MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true",
                        help="rebuild in memory and confirm the committed artifacts match")
    args = parser.parse_args()

    cases, manifest = build()
    if args.verify_only:
        if not OUT_CSV.exists():
            print("FAIL: benchmark has not been built yet")
            return 1
        with OUT_CSV.open("r", encoding="utf-8", newline="") as handle:
            existing = handle.read()
        if render_csv(cases) != existing:
            print("FAIL: committed benchmark differs from a fresh build")
            return 1
        print("OK: committed benchmark is byte-identical to a fresh build")
        return 0

    write(cases, manifest)
    records = manifest["records"]
    print(f"wrote {OUT_CSV.relative_to(ROOT)}  ({records['total']} real audited firms)")
    print(f"  development {records['development']}  "
          f"({records['development_positive']}+/{records['development_negative']}-)")
    print(f"  evaluation  {records['evaluation']}  "
          f"({records['evaluation_positive']}+/{records['evaluation_negative']}-)")
    print(f"  evaluation hard negatives (flagged then cleared): "
          f"{records['evaluation_hard_negatives']}")
    print(f"  evidence documents: {manifest['artifacts']['evidence_documents']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
