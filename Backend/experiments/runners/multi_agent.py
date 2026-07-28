from __future__ import annotations

from collections.abc import Callable

from experiments.runners.base import ExperimentConfig
from experiments.runners.single_llm import run as run_adapter


def run(rows: list[dict[str, str]], orchestrate: Callable[[dict[str, str], ExperimentConfig], dict],
        config: ExperimentConfig) -> list:
    """Config-aware research adapter for the live graph or a mocked orchestrator."""
    def invoke(row: dict[str, str]) -> dict:
        return orchestrate(row, config)

    results = run_adapter(rows, invoke, provider=config.provider, model=config.model,
                          prompt_version=config.prompt_version)
    for result in results:
        result.method = config.method
    return results
