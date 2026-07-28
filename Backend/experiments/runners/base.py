from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ExperimentConfig:
    method: str
    provider: str
    model: str
    temperature: float
    max_tokens: int
    retrieval_enabled: bool
    challenger_enabled: bool
    defender_enabled: bool
    verifier_enabled: bool
    debate_rounds: int
    confidence_threshold: float
    prompt_version: str
    dataset_version: str
    split_seed: int
    timeout_seconds: int
    retries: int

    def validate(self) -> None:
        if not self.method or not 0 <= self.temperature <= 2 or not 0 <= self.confidence_threshold <= 1:
            raise ValueError("invalid experiment configuration")
        if self.debate_rounds < 0 or self.max_tokens <= 0 or self.timeout_seconds <= 0 or self.retries < 0:
            raise ValueError("invalid experiment limits")


def load_config(path: Path) -> ExperimentConfig:
    # JSON is valid YAML 1.2 and avoids a runtime PyYAML dependency.
    config = ExperimentConfig(**json.loads(path.read_text(encoding="utf-8")))
    config.validate()
    return config
