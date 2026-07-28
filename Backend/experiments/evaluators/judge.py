"""LLM-as-judge scoring for groundedness and citation correctness.

Protocol
--------
The judge sees the evidence documents, the system's explanation, and the citations it
made. It never sees the gold label, the system's own prediction, or which method produced
the answer, so it cannot reward a verdict for being correct rather than supported.

Two independent judges are run by default, on different models. Their agreement is
reported (percentage and quadratic-weighted Cohen's kappa over the three-point rubric),
and the item is scored as the mean of the two only when they agree within one rubric step.
Larger disagreements are exported for human adjudication rather than silently averaged.

Rubric, deliberately three-point so that human adjudication is tractable:

``1.0``  every factual claim is supported by a cited document
``0.5``  the central claim is supported; some subsidiary claims are not
``0.0``  the central claim is not supported by anything cited
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from experiments.llm import Provider, ProviderError, _first_json_object

PROMPT_DIR = Path(__file__).resolve().parent / "judge_prompts"

VALID_SCORES = (0.0, 0.5, 1.0)


@dataclass
class Judgment:
    transaction_id: str
    judge: str
    model: str
    groundedness: float | None
    citation_correctness: float | None
    reasoning: str = ""
    error: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    def to_dict(self) -> dict:
        return {
            "transaction_id": self.transaction_id, "judge": self.judge, "model": self.model,
            "groundedness": self.groundedness,
            "citation_correctness": self.citation_correctness,
            "reasoning": self.reasoning, "error": self.error,
            "input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
        }


@dataclass
class AdjudicationRow:
    transaction_id: str
    metric: str
    scores: dict[str, float]
    resolved: float | None
    needs_human: bool
    gap: float
    notes: str = ""


JUDGE_SYSTEM = """\
You are evaluating the *evidential support* of an audit explanation. You are not judging
whether its conclusion is right, and you are not told what the correct answer is. An
explanation that reaches the wrong conclusion from correctly cited evidence scores well;
one that reaches the right conclusion from nothing scores badly.

Score two things on the three-point scale {0, 0.5, 1}:

groundedness
  1.0  every factual claim in the explanation is supported by one of the cited documents
  0.5  the central claim is supported; one or more subsidiary claims are not
  0.0  the central claim is not supported by any cited document, or nothing was cited

citation_correctness
  1.0  every cited document actually supports the claim it is attached to
  0.5  at least one citation is relevant but does not fully support its claim
  0.0  the citations do not support the claims, or refer to documents not provided

Respond with a single JSON object and nothing else:

{"groundedness": 0|0.5|1, "citation_correctness": 0|0.5|1, "reasoning": "two sentences"}
"""


def render_judge_prompt(evidence: dict[str, str], explanation: str,
                        citations: list[str]) -> str:
    lines = ["EVIDENCE DOCUMENTS AVAILABLE FOR THIS CASE"]
    if evidence:
        for key in sorted(evidence):
            lines.append(f"[{key}] {evidence[key]}")
    else:
        lines.append("(none were available to the system)")
    lines += ["", "CITATIONS MADE BY THE SYSTEM"]
    lines.append(", ".join(citations) if citations else "(none)")
    lines += ["", "EXPLANATION UNDER REVIEW", explanation or "(empty)"]
    return "\n".join(lines)


def _parse_scores(text: str) -> tuple[float, float, str]:
    candidate = _first_json_object(text)
    if candidate is None:
        raise ValueError("judge response contained no JSON object")
    data = json.loads(candidate)
    scores = []
    for key in ("groundedness", "citation_correctness"):
        if key not in data:
            raise ValueError(f"judge response is missing {key}")
        value = float(data[key])
        if value not in VALID_SCORES:
            raise ValueError(f"{key}={value} is not on the rubric scale {VALID_SCORES}")
        scores.append(value)
    return scores[0], scores[1], str(data.get("reasoning", "")).strip()


def judge_row(provider: Provider, judge_name: str, transaction_id: str,
              evidence: dict[str, str], explanation: str,
              citations: list[str]) -> Judgment:
    prompt = render_judge_prompt(evidence, explanation, citations)
    try:
        completion = provider.complete(JUDGE_SYSTEM, prompt)
    except ProviderError as exc:
        return Judgment(transaction_id, judge_name, provider.config.model, None, None,
                        error=f"provider_failure:{exc}")
    try:
        groundedness, citation, reasoning = _parse_scores(completion.text)
    except (ValueError, json.JSONDecodeError) as exc:
        return Judgment(transaction_id, judge_name, provider.config.model, None, None,
                        error=f"parse_failure:{exc}",
                        input_tokens=completion.input_tokens,
                        output_tokens=completion.output_tokens,
                        cost_usd=completion.cost_usd)
    return Judgment(transaction_id, judge_name, provider.config.model, groundedness,
                    citation, reasoning=reasoning,
                    input_tokens=completion.input_tokens,
                    output_tokens=completion.output_tokens, cost_usd=completion.cost_usd)


def reconcile(judgments: dict[str, list[Judgment]], metric: str,
              tolerance: float = 0.5) -> list[AdjudicationRow]:
    """Combine judges per item; flag anything further apart than one rubric step."""
    rows: list[AdjudicationRow] = []
    for transaction_id, items in sorted(judgments.items()):
        scores = {j.judge: getattr(j, metric) for j in items
                  if getattr(j, metric) is not None}
        if not scores:
            rows.append(AdjudicationRow(transaction_id, metric, {}, None, True, 0.0,
                                        notes="no judge produced a usable score"))
            continue
        values = list(scores.values())
        gap = max(values) - min(values)
        needs_human = gap > tolerance
        resolved = None if needs_human else round(sum(values) / len(values), 4)
        rows.append(AdjudicationRow(
            transaction_id, metric, scores, resolved, needs_human, round(gap, 4),
            notes="" if not needs_human
            else f"judges differ by {gap} on the three-point rubric; human decision required"))
    return rows


@dataclass
class AgreementReport:
    metric: str
    judge_a: str
    judge_b: str
    n: int
    percentage_agreement: float | None = None
    cohens_kappa_quadratic: float | None = None
    exact_match: int = 0
    within_one_step: int = 0
    escalated_to_human: int = 0
    resolved_automatically: int = 0
    distribution: dict[str, dict[str, int]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return self.__dict__ | {}
