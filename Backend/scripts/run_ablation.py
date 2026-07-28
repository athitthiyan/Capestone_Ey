from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from experiments.runners import load_config

if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("config", type=Path); args = parser.parse_args()
    config = load_config(args.config)
    print(f"{config.method}: configuration valid; live ablation Not run")
