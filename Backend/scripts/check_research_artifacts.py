from __future__ import annotations

import csv
import hashlib
import json
import tempfile
from pathlib import Path

from generate_benchmark_dataset import write_dataset


def main() -> None:
    dataset = Path("datasets/gl_guardian_benchmark_v1.csv")
    manifest = json.loads(dataset.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    if hashlib.sha256(dataset.read_bytes()).hexdigest() != manifest["sha256"]:
        raise SystemExit("dataset digest does not match manifest")
    with tempfile.TemporaryDirectory() as folder:
        candidate = Path(folder) / "dataset.csv"; regenerated = write_dataset(candidate)
        if regenerated["sha256"] != manifest["sha256"]:
            raise SystemExit("dataset generation is not reproducible")
    summary = json.loads(Path("experiments/results/summary.json").read_text(encoding="utf-8"))
    with Path("experiments/results/metrics.csv").open(encoding="utf-8", newline="") as handle:
        metrics = next(csv.DictReader(handle))
    if abs(float(metrics["accuracy"]) - summary["classification"]["accuracy"]) > 1e-12:
        raise SystemExit("metrics.csv and summary.json disagree")
    if summary["executed_methods"] != ["rule_baseline"]:
        raise SystemExit("unexpected claim about executed methods")
    readme = Path("../README.md").read_text(encoding="utf-8")
    # The README reports the primary real-label UCI benchmark. Keep those
    # headline numbers synchronized when that artifact is present; the root
    # summary above remains the credential-free synthetic smoke experiment.
    primary_path = Path("experiments/results/uci_audit_v1/summary.json")
    if primary_path.exists():
        primary = json.loads(primary_path.read_text(encoding="utf-8"))
        rule = primary.get("methods", {}).get("rule_baseline", {})
        classification = rule.get("classification", rule)
        for name in ("accuracy", "precision", "recall", "specificity", "f1", "mcc"):
            value = classification.get(name)
            if value is not None and f"{value:.3f}" not in readme:
                raise SystemExit(f"README does not contain generated UCI {name}")
    print("research artifacts are reproducible and internally consistent")


if __name__ == "__main__": main()
