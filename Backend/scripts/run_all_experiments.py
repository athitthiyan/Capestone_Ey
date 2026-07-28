from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from experiments.runners import load_config


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--dry-run", action="store_true"); args = parser.parse_args()
    statuses = []
    for path in sorted(Path("experiments/configs").glob("*.yaml")):
        config = load_config(path)
        if config.method == "rule_baseline" and not args.dry_run:
            status = "execute with: python scripts/run_rule_baseline.py"
        elif args.dry_run:
            status = "configuration validated; live result Not run"
        else:
            status = "Not run: configure provider credentials and method adapter"
        statuses.append({"method": config.method, "status": status})
    print(json.dumps(statuses, indent=2))


if __name__ == "__main__": main()
