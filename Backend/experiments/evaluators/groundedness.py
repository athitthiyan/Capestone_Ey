from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GroundednessJudgment:
    score: float
    reasoning: str
    judge: str
    prompt_version: str
    requires_human_review: bool = True


def score_groundedness(claims: list[dict], evidence: dict[str, str]) -> GroundednessJudgment:
    """Deterministic rubric for fixtures; live judge outputs require human review.

    Classification labels are intentionally absent from this interface.
    """
    if not claims:
        return GroundednessJudgment(0.0, "No auditable claims were supplied.", "rubric", "groundedness-v1")
    supported = 0.0
    details = []
    for claim in claims:
        citations = claim.get("citations") or []
        matches = [citation for citation in citations if citation in evidence and evidence[citation].strip()]
        fraction = 1.0 if matches else 0.0
        supported += fraction
        details.append(f"{claim.get('claim_id', 'claim')}: {'supported' if matches else 'unsupported'}")
    raw = supported / len(claims)
    score = 1.0 if raw == 1 else 0.5 if raw > 0 else 0.0
    return GroundednessJudgment(score, "; ".join(details), "rubric", "groundedness-v1")
