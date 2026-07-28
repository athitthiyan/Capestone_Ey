from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CitationJudgment:
    score: float
    reasoning: str
    judge: str = "rubric"
    prompt_version: str = "citation-v1"
    requires_human_review: bool = True


def score_citations(claims: list[dict], evidence: dict[str, str]) -> CitationJudgment:
    if not claims:
        return CitationJudgment(0.0, "No claims were supplied.")
    scores, notes = [], []
    for claim in claims:
        text = str(claim.get("text", "")).lower()
        citations = claim.get("citations") or []
        best = 0.0
        for citation in citations:
            source = evidence.get(citation, "").lower()
            overlap = set(text.split()) & set(source.split())
            if source and overlap:
                best = max(best, 1.0 if len(overlap) >= 3 else 0.5)
        scores.append(best); notes.append(f"{claim.get('claim_id', 'claim')}={best}")
    average = sum(scores) / len(scores)
    score = 1.0 if average == 1 else 0.5 if average > 0 else 0.0
    return CitationJudgment(score, "; ".join(notes))
