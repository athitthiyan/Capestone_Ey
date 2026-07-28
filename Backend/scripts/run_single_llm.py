"""Validate the single-LLM configuration; live calls require provider credentials."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from experiments.runners import load_config

if __name__ == "__main__":
    config = load_config(Path("experiments/configs/single_llm.yaml"))
    print(f"{config.method}: Not run; set provider credentials and USE_REAL_AGENTS=true")
