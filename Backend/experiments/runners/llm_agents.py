"""Live single-LLM and multi-agent runners.

Both runners consume :class:`~experiments.benchmarks.BenchmarkCase` objects and can only
see ``case.model_view()``, so the label cannot reach the prompt even by accident. The
ablation switches on :class:`~experiments.runners.base.ExperimentConfig` map onto real
structural changes:

============================  ==================================================
``retrieval_enabled=False``   evidence documents are withheld; only the recorded
                              fields are shown (the no-RAG condition)
``challenger_enabled=False``  no rebuttal turn is generated
``defender_enabled=False``    no response-to-rebuttal turn is generated
``verifier_enabled=False``    the last debating agent's verdict stands, with no
                              independent citation check
``debate_rounds=N``           challenger/defender exchange repeats N times
============================  ==================================================

A response that cannot be parsed is recorded as an error row with the raw text kept for
failure analysis. It is never replaced with a guessed prediction.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from experiments.benchmarks import BenchmarkCase
from experiments.llm import Completion, ParsedVerdict, Provider, ProviderError, parse_verdict
from experiments.runners.base import ExperimentConfig
from experiments.schema import ExperimentResult

PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"

FIELD_LABELS = {
    "para_a_discrepancy_cr": "Planned-audit para discrepancy (crore INR)",
    "para_b_discrepancy_cr": "Unplanned-audit para discrepancy (crore INR)",
    "total_discrepancy_cr": "Total reported discrepancy (crore INR)",
    "discrepancy_count": "Number of distinct discrepancy findings",
    "money_value_cr": "Money value of misstatements in prior audits (crore INR)",
    "district_loss_score": "District loss indicator",
    "history_score": "Historical discrepancy record",
    "sector_score": "Sector historical risk score",
    "location_id": "Location identifier",
    "prior_screen_flag": "Pre-audit screen flagged this case (1 = yes)",
    "prior_screen_score": "Pre-audit screen score",
    "amount_usd": "Transaction amount (USD)",
    "vendor_id": "Vendor identifier",
    "document_status": "Supporting document status",
    "po_number": "Purchase order reference",
    "payment_method": "Payment method",
    "posted_by": "Posted by",
    "approved_by": "Approved by",
    "related_party_flag": "Related-party indicator",
    "duplicate_of": "Marked as duplicate of",
    "currency": "Currency",
}

HIDDEN_FIELDS = frozenset({"transaction_id", "evidence_ids"})


def _read_prompt(name: str) -> str:
    path = PROMPT_DIR / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"prompt {name} is missing at {path}")
    return path.read_text(encoding="utf-8").strip()


def prompt_version(*names: str) -> str:
    """Version string tied to the *content* of the prompts actually used."""
    digest = hashlib.sha256()
    for name in names:
        digest.update(name.encode("utf-8"))
        digest.update(_read_prompt(name).encode("utf-8"))
    return f"{'+'.join(names)}@{digest.hexdigest()[:8]}"


def render_case(case: BenchmarkCase, corpus: dict[str, str], *,
                include_evidence: bool) -> str:
    view = case.model_view()
    lines = [f"CASE {case.case_id}", "", "RECORDED FIELDS"]
    for key, value in view.items():
        if key in HIDDEN_FIELDS or value in ("", None):
            continue
        lines.append(f"- {FIELD_LABELS.get(key, key)}: {value}")

    if include_evidence:
        documents = case.evidence(corpus)
        lines += ["", "EVIDENCE"]
        if documents:
            for key in sorted(documents):
                lines.append(f"[{key}] {documents[key]}")
        else:
            lines.append("(no evidence documents are available for this case)")
    else:
        lines += ["", "EVIDENCE",
                  "(no evidence retrieval is available in this configuration; reason from the "
                  "recorded fields only and cite nothing)"]
    return "\n".join(lines)


def allowed_citations(case: BenchmarkCase, corpus: dict[str, str], *,
                      include_evidence: bool) -> set[str]:
    return set(case.evidence(corpus)) if include_evidence else set()


@dataclass
class Turn:
    role: str
    text: str
    completion: Completion


class _Accumulator:
    """Aggregates usage across the turns that make up one case verdict."""

    def __init__(self) -> None:
        self.input_tokens = 0
        self.output_tokens = 0
        self.cost_usd = 0.0
        self.latency_ms = 0.0
        self.turns: list[Turn] = []

    def add(self, role: str, completion: Completion) -> Turn:
        self.input_tokens += completion.input_tokens
        self.output_tokens += completion.output_tokens
        self.cost_usd += completion.cost_usd
        self.latency_ms += completion.latency_ms
        turn = Turn(role=role, text=completion.text, completion=completion)
        self.turns.append(turn)
        return turn


def _result(case: BenchmarkCase, method: str, verdict: ParsedVerdict | None,
            usage: _Accumulator, config: ExperimentConfig, run_id: str,
            version: str, wall_ms: float, error: str = "",
            transcript: str = "") -> ExperimentResult:
    result = ExperimentResult(
        transaction_id=case.case_id, method=method,
        prediction=verdict.prediction if verdict else 0,
        confidence=verdict.confidence if verdict else 0.0,
        explanation=verdict.explanation if verdict else transcript[:2000],
        evidence_ids=list(case.evidence_ids),
        citations=list(verdict.citations) if verdict else [],
        input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
        cost_usd=round(usage.cost_usd, 8), latency_ms=wall_ms,
        model=config.model, provider=config.provider, prompt_version=version,
        run_id=run_id, error=error,
    )
    result.validate()
    return result


def run_single_llm(cases: Sequence[BenchmarkCase], provider: Provider,
                   corpus: dict[str, str], config: ExperimentConfig) -> list[ExperimentResult]:
    version = prompt_version("single_llm_v1", "output_contract_v1")
    system = _read_prompt("single_llm_v1") + "\n\n" + _read_prompt("output_contract_v1")
    run_id = f"single-{uuid4().hex[:12]}"
    results: list[ExperimentResult] = []

    for case in cases:
        usage = _Accumulator()
        started = time.perf_counter()
        user = render_case(case, corpus, include_evidence=config.retrieval_enabled)
        allowed = allowed_citations(case, corpus, include_evidence=config.retrieval_enabled)
        try:
            completion = provider.complete(system, user)
            usage.add("single", completion)
            verdict = parse_verdict(completion.text, allowed_citations=allowed)
            results.append(_result(case, config.method, verdict, usage, config, run_id,
                                   version, (time.perf_counter() - started) * 1000))
        except ProviderError as exc:
            results.append(_result(case, config.method, None, usage, config, run_id, version,
                                   (time.perf_counter() - started) * 1000,
                                   error=f"provider_failure:{exc}"))
        except (ValueError, KeyError, TypeError) as exc:
            raw = usage.turns[-1].text if usage.turns else ""
            results.append(_result(case, config.method, None, usage, config, run_id, version,
                                   (time.perf_counter() - started) * 1000,
                                   error=f"parse_failure:{type(exc).__name__}:{exc}",
                                   transcript=raw))
    return results


def run_multi_agent(cases: Sequence[BenchmarkCase], provider: Provider,
                    corpus: dict[str, str], config: ExperimentConfig) -> list[ExperimentResult]:
    names = ["detective_v1"]
    if config.challenger_enabled:
        names.append("challenger_v1")
    if config.defender_enabled:
        names.append("defender_v1")
    if config.verifier_enabled:
        names.append("verifier_v1")
    names.append("output_contract_v1")
    version = prompt_version(*names)
    contract = _read_prompt("output_contract_v1")
    run_id = f"{config.method}-{uuid4().hex[:12]}"
    results: list[ExperimentResult] = []

    for case in cases:
        usage = _Accumulator()
        started = time.perf_counter()
        user = render_case(case, corpus, include_evidence=config.retrieval_enabled)
        allowed = allowed_citations(case, corpus, include_evidence=config.retrieval_enabled)
        transcript: list[str] = []
        try:
            detective = provider.complete(
                _read_prompt("detective_v1") + "\n\n" + contract, user)
            usage.add("detective", detective)
            transcript.append(f"DETECTIVE:\n{detective.text}")
            last_verdict_text = detective.text

            for round_index in range(max(0, config.debate_rounds)):
                if config.challenger_enabled:
                    challenger = provider.complete(
                        _read_prompt("challenger_v1") + "\n\n" + contract,
                        f"{user}\n\nDEBATE SO FAR (round {round_index + 1})\n"
                        + "\n\n".join(transcript))
                    usage.add(f"challenger_r{round_index + 1}", challenger)
                    transcript.append(f"CHALLENGER (round {round_index + 1}):\n{challenger.text}")
                    last_verdict_text = challenger.text
                if config.defender_enabled:
                    defender = provider.complete(
                        _read_prompt("defender_v1") + "\n\n" + contract,
                        f"{user}\n\nDEBATE SO FAR (round {round_index + 1})\n"
                        + "\n\n".join(transcript))
                    usage.add(f"defender_r{round_index + 1}", defender)
                    transcript.append(f"DEFENDER (round {round_index + 1}):\n{defender.text}")
                    last_verdict_text = defender.text

            if config.verifier_enabled:
                verifier = provider.complete(
                    _read_prompt("verifier_v1") + "\n\n" + contract,
                    f"{user}\n\nDEBATE TRANSCRIPT\n" + "\n\n".join(transcript))
                usage.add("verifier", verifier)
                transcript.append(f"VERIFIER:\n{verifier.text}")
                last_verdict_text = verifier.text

            verdict = parse_verdict(last_verdict_text, allowed_citations=allowed)
            results.append(_result(case, config.method, verdict, usage, config, run_id,
                                   version, (time.perf_counter() - started) * 1000))
        except ProviderError as exc:
            results.append(_result(case, config.method, None, usage, config, run_id, version,
                                   (time.perf_counter() - started) * 1000,
                                   error=f"provider_failure:{exc}"))
        except (ValueError, KeyError, TypeError) as exc:
            results.append(_result(case, config.method, None, usage, config, run_id, version,
                                   (time.perf_counter() - started) * 1000,
                                   error=f"parse_failure:{type(exc).__name__}:{exc}",
                                   transcript="\n\n".join(transcript)))
    return results
