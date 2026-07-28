from __future__ import annotations

import csv
import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.runners.rule import run


def main() -> None:
    dataset = Path("datasets/gl_guardian_benchmark_v1.csv")
    with dataset.open(encoding="utf-8", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if row["split"] == "evaluation"]
    results = run(rows); output = Path("experiments/runs/rule_baseline.jsonl"); output.parent.mkdir(parents=True, exist_ok=True)
    config_path = Path("experiments/configs/rule_baseline.yaml")
    config_sha = hashlib.sha256(config_path.read_bytes()).hexdigest()
    for result in results:
        result.resolved_config_sha256 = config_sha
    output.write_text("".join(json.dumps(asdict(row), sort_keys=True) + "\n" for row in results), encoding="utf-8")
    resolved = Path("experiments/runs/rule_baseline.config.json")
    resolved.write_text(config_path.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"wrote {len(results)} predictions to {output}")


if __name__ == "__main__": main()
