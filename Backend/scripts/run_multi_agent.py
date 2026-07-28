"""Validate full multi-agent configuration; never substitutes fixture metrics."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from experiments.runners import load_config

if __name__ == "__main__":
    config = load_config(Path("experiments/configs/full_multi_agent.yaml"))
    print(f"{config.method}: Not run; execute through the live GL Guardian API after credentials")
