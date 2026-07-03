"""Real-time RAGAS evaluation via an LLM judge.

This is the "real" counterpart to ``app/evaluation/ragas.py``'s telemetry
proxies - it calls the actual `ragas` metric implementations (LLM-as-judge,
not a hand-rolled ratio) against what a specific investigation actually
produced, right after that investigation finishes.

Six metrics need no reference/ground-truth answer and can be scored the
moment an investigation completes:

* Faithfulness            - are the verdict's claims supported by the evidence?
* Response Relevancy      - does the verdict actually answer the audit question?
* Context Precision       - was the retrieved policy/evidence context relevant?
* Tool Call Accuracy      - did the crew actually invoke evidence retrieval,
                            in the right order?
* Topic Adherence         - did the debate stay within audit scope?
* Agent Goal Accuracy     - did the crew reach a fully-supported decision?

Three metrics fundamentally require a reference answer to compare against and
only become scoreable once a human reviewer sets one (see
``Investigation.ground_truth_verdict``, set from the review approve/reject
routes):

* Factual Correctness
* Semantic Similarity
* Context Entity Recall

The remaining catalog metric, Context Recall, has no honest no-reference
formulation in ragas that fits this system (every variant wants either a
reference answer or a reference set of "correct" chunks we don't have) - it
stays on the existing telemetry proxy in ragas.py.

The judge LLM is always Anthropic, regardless of which provider produced the
response being judged, so scores are comparable across providers rather than
each provider grading its own work.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from functools import lru_cache

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import DebateTranscript, EvidenceArtifact, Investigation, LLMCallLog

logger = logging.getLogger(__name__)

# Fixed, case-independent scope for Topic Adherence. This crew always
# investigates the same kind of question, so "what's on topic" is a property
# of the crew's job, not a per-case label - it doesn't need a human reference.
AUDIT_TOPICS: list[str] = [
    "transaction legitimacy",
    "vendor authorization",
    "materiality threshold",
    "policy compliance",
    "fraud risk",
    "control weakness",
    "evidence sufficiency",
]

# EvidenceArtifact.source values that represent a genuine retrieval/tool
# action (as opposed to deterministic ledger/intake facts the crew already
# had on hand without calling anything).
_NON_TOOL_SOURCES = {"ledger_row", "intake_prefilter"}


def _is_tool_sourced(source: str) -> bool:
    return source not in _NON_TOOL_SOURCES


@dataclass(frozen=True)
class ScoredCase:
    """Everything pulled from the DB needed to build ragas samples for one investigation."""

    investigation: Investigation
    evidence: list[EvidenceArtifact]
    debates: list[DebateTranscript]
    scored_provider: str | None
    scored_model: str | None


def _audit_question(investigation: Investigation) -> str:
    return (
        f"Is the {investigation.category} transaction {investigation.transaction_id} "
        f"for ${investigation.amount:,.2f} to vendor {investigation.vendor} "
        f"(materiality threshold ${investigation.materiality or 0:,.2f}) legitimate and "
        f"properly authorized, or does it present an audit risk?"
    )


def _verdict_response(debates: list[DebateTranscript]) -> str | None:
    verdicts = [d for d in debates if (d.speaker or "").lower() == "adjudicator"]
    if not verdicts:
        return None
    return sorted(verdicts, key=lambda d: d.created_at or 0)[-1].message


def _retrieved_contexts(evidence: list[EvidenceArtifact]) -> list[str]:
    contexts = [e.content for e in evidence if e.content]
    return contexts or ["No evidence was retrieved for this case."]


def _scored_llm(db: Session, investigation_id: str) -> tuple[str | None, str | None]:
    """Which provider/model actually produced the adjudication being judged.

    Looked up from LLMCallLog (keyed by the investigation_id column - see
    migration 20260704_0004) rather than threaded through from the executor,
    so this works the same whether the investigation ran via Celery, inline,
    or (in tests) with mocked agents that never call an LLM at all.
    """
    row = (
        db.query(LLMCallLog)
        .filter(
            LLMCallLog.investigation_id == investigation_id,
            LLMCallLog.request_type == "adjudication",
            LLMCallLog.success.is_(True),
        )
        .order_by(LLMCallLog.created_at.desc())
        .first()
    )
    if row is None:
        return None, None
    return row.provider_name, row.model_name


def load_scored_case(db: Session, investigation_id: str) -> ScoredCase | None:
    investigation = db.get(Investigation, investigation_id)
    if investigation is None:
        return None
    evidence = (
        db.query(EvidenceArtifact)
        .filter(EvidenceArtifact.investigation_id == investigation_id)
        .order_by(EvidenceArtifact.created_at.asc())
        .all()
    )
    debates = (
        db.query(DebateTranscript)
        .filter(DebateTranscript.investigation_id == investigation_id)
        .order_by(DebateTranscript.round.asc(), DebateTranscript.created_at.asc())
        .all()
    )
    provider, model = _scored_llm(db, investigation_id)
    return ScoredCase(
        investigation=investigation,
        evidence=evidence,
        debates=debates,
        scored_provider=provider,
        scored_model=model,
    )


class _HashEmbeddings:
    """Lightweight embeddings for ragas's embedding-based metrics.

    Wraps the deterministic hash embedding already used for local knowledge
    retrieval (app.knowledge.retriever.embed_text) instead of requiring an
    OpenAI embeddings key or a heavy sentence-transformers model - consistent
    with this codebase's "dependency-light" retrieval design.
    """

    def embed_query(self, text: str) -> list[float]:
        from app.knowledge.retriever import embed_text

        return embed_text(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        from app.knowledge.retriever import embed_text

        return [embed_text(t) for t in texts]

    async def aembed_query(self, text: str) -> list[float]:
        return await asyncio.to_thread(self.embed_query, text)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self.embed_documents, texts)


@lru_cache(maxsize=1)
def _judge_llm():
    from langchain_anthropic import ChatAnthropic
    from ragas.llms import LangchainLLMWrapper

    model = settings.RAGAS_JUDGE_MODEL or settings.CLAUDE_MODEL_REASONING
    chat = ChatAnthropic(
        model=model,
        anthropic_api_key=settings.ANTHROPIC_API_KEY,
        temperature=0.0,
        max_tokens=1024,
        default_request_timeout=settings.RAGAS_JUDGE_TIMEOUT_SECONDS,
    )
    return LangchainLLMWrapper(chat)


@lru_cache(maxsize=1)
def _judge_embeddings():
    from ragas.embeddings import LangchainEmbeddingsWrapper

    # LangchainEmbeddingsWrapper expects a langchain Embeddings object; our
    # _HashEmbeddings duck-types the sync methods it actually calls
    # (embed_query/embed_documents), which is all SemanticSimilarity/
    # ResponseRelevancy need.
    return LangchainEmbeddingsWrapper(_HashEmbeddings())


def judge_available() -> bool:
    return bool(settings.RAGAS_REALTIME_ENABLED and settings.ANTHROPIC_API_KEY.strip())


# --------------------------------------------------------------------------
# Sample construction
# --------------------------------------------------------------------------


def _single_turn_sample(case: ScoredCase, reference: str | None = None):
    from ragas.dataset_schema import SingleTurnSample

    return SingleTurnSample(
        user_input=_audit_question(case.investigation),
        response=_verdict_response(case.debates),
        retrieved_contexts=_retrieved_contexts(case.evidence),
        reference=reference,
    )


def _debate_conversation(case: ScoredCase):
    from ragas.messages import AIMessage, HumanMessage

    messages = [HumanMessage(content=_audit_question(case.investigation))]
    for row in case.debates:
        speaker = (row.speaker or "agent").lower()
        messages.append(AIMessage(content=f"[{speaker}] {row.message}"))
    return messages


def _tool_call_sample(case: ScoredCase):
    from ragas.dataset_schema import MultiTurnSample
    from ragas.messages import AIMessage, HumanMessage, ToolCall

    # Args are intentionally empty on both sides: this system doesn't log the
    # literal retrieval query per call, so claiming an exact-arg match would
    # overstate precision. Name + sequence (was retrieval invoked, in the
    # right relative position) is the real, honest signal here.
    predicted = [
        ToolCall(name="retrieve_knowledge_context", args={})
        for row in case.evidence
        if _is_tool_sourced(row.source)
    ]
    reference = [ToolCall(name="retrieve_knowledge_context", args={})]
    messages = [
        HumanMessage(content=_audit_question(case.investigation)),
        AIMessage(content="Collecting evidence.", tool_calls=predicted or None),
    ]
    return MultiTurnSample(user_input=messages, reference_tool_calls=reference)


def _topic_sample(case: ScoredCase):
    from ragas.dataset_schema import MultiTurnSample

    return MultiTurnSample(user_input=_debate_conversation(case), reference_topics=AUDIT_TOPICS)


def _goal_sample(case: ScoredCase):
    from ragas.dataset_schema import MultiTurnSample

    return MultiTurnSample(user_input=_debate_conversation(case))


# --------------------------------------------------------------------------
# Per-metric scorers - each catches its own exceptions so one bad judge call
# (timeout, malformed judge output, provider hiccup) doesn't take the whole
# batch down; a failed metric is simply omitted rather than faked.
# --------------------------------------------------------------------------


async def _safe_single_turn(metric, sample, label: str, investigation_id: str) -> float | None:
    if sample.response is None:
        return None
    try:
        return float(await metric.single_turn_ascore(sample))
    except Exception as exc:  # noqa: BLE001
        logger.warning("RAGAS %s failed for %s: %s", label, investigation_id, exc)
        return None


async def _safe_multi_turn(metric, sample, label: str, investigation_id: str) -> float | None:
    try:
        return float(await metric.multi_turn_ascore(sample))
    except Exception as exc:  # noqa: BLE001
        logger.warning("RAGAS %s failed for %s: %s", label, investigation_id, exc)
        return None


async def score_realtime_metrics(case: ScoredCase) -> dict[str, float | None]:
    """The 6 metrics scoreable with no reference answer, run concurrently."""
    from ragas.metrics import (
        AgentGoalAccuracyWithoutReference,
        Faithfulness,
        LLMContextPrecisionWithoutReference,
        ResponseRelevancy,
        ToolCallAccuracy,
        TopicAdherenceScore,
    )

    inv_id = case.investigation.id
    llm = _judge_llm()

    faithfulness = Faithfulness()
    faithfulness.llm = llm

    precision = LLMContextPrecisionWithoutReference()
    precision.llm = llm

    relevancy = ResponseRelevancy()
    relevancy.llm = llm
    relevancy.embeddings = _judge_embeddings()

    topic = TopicAdherenceScore()
    topic.llm = llm

    goal = AgentGoalAccuracyWithoutReference()
    goal.llm = llm

    tool_accuracy = ToolCallAccuracy()

    single_turn_sample = _single_turn_sample(case)

    results = await asyncio.gather(
        _safe_single_turn(faithfulness, single_turn_sample, "Faithfulness", inv_id),
        _safe_single_turn(precision, single_turn_sample, "Context Precision", inv_id),
        _safe_single_turn(relevancy, single_turn_sample, "Response Relevancy", inv_id),
        _safe_multi_turn(tool_accuracy, _tool_call_sample(case), "Tool Call Accuracy", inv_id),
        _safe_multi_turn(topic, _topic_sample(case), "Topic Adherence", inv_id),
        _safe_multi_turn(goal, _goal_sample(case), "Agent Goal Accuracy", inv_id),
    )
    return {
        "Faithfulness": results[0],
        "Context Precision": results[1],
        "Response Relevancy": results[2],
        "Tool Call Accuracy": results[3],
        "Topic Adherence": results[4],
        "Agent Goal Accuracy": results[5],
    }


async def score_reference_metrics(case: ScoredCase, reference: str) -> dict[str, float | None]:
    """The 3 metrics that need a human-confirmed ground-truth verdict."""
    from ragas.metrics import ContextEntityRecall, FactualCorrectness, SemanticSimilarity

    inv_id = case.investigation.id
    llm = _judge_llm()

    entity_recall = ContextEntityRecall()
    entity_recall.llm = llm

    correctness = FactualCorrectness()
    correctness.llm = llm

    similarity = SemanticSimilarity()
    similarity.embeddings = _judge_embeddings()

    sample = _single_turn_sample(case, reference=reference)

    results = await asyncio.gather(
        _safe_single_turn(entity_recall, sample, "Context Entity Recall", inv_id),
        _safe_single_turn(correctness, sample, "Factual Correctness", inv_id),
        _safe_single_turn(similarity, sample, "Semantic Similarity", inv_id),
    )
    return {
        "Context Entity Recall": results[0],
        "Factual Correctness": results[1],
        "Semantic Similarity": results[2],
    }
