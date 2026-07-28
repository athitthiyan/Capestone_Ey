from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ExperimentResult:
    transaction_id: str
    method: str
    prediction: int
    confidence: float
    explanation: str = ""
    evidence_ids: list[str] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    groundedness: float | None = None
    citation_correctness: float | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    model: str = "none"
    provider: str = "none"
    prompt_version: str = "v1"
    run_id: str = ""
    experiment_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    random_seed: int = 20260728
    resolved_config_sha256: str = ""
    error: str = ""

    def validate(self) -> None:
        if not self.transaction_id:
            raise ValueError("transaction_id is required")
        if self.prediction not in (0, 1):
            raise ValueError("prediction must be 0 or 1")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be in [0, 1]")
        for name in ("groundedness", "citation_correctness"):
            value = getattr(self, name)
            if value is not None and not 0 <= value <= 1:
                raise ValueError(f"{name} must be in [0, 1]")
        if self.cost_usd < 0 or self.latency_ms < 0:
            raise ValueError("cost and latency must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)
