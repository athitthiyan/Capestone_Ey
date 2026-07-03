"""Real-time RAGAS LLM-judge tests (app/evaluation/ragas_judge.py).

Every ragas metric call is mocked so this suite makes zero real LLM API
calls, consistent with the rest of the suite's USE_REAL_AGENTS=false,
no-network convention. These tests cover sample construction and the
scorer functions' exception-handling behavior (a judge failure on one
metric must return None for that metric, not raise or take down the rest
of the batch).
"""

import asyncio
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, DebateTranscript, EvidenceArtifact, Investigation
from app.evaluation import ragas_judge as rj

REALTIME_METRIC_PATCHES = dict(
    faithfulness=("ragas.metrics.Faithfulness.single_turn_ascore", 0.9),
    precision=("ragas.metrics.LLMContextPrecisionWithoutReference.single_turn_ascore", 0.8),
    relevancy=("ragas.metrics.ResponseRelevancy.single_turn_ascore", 0.7),
    tool_accuracy=("ragas.metrics.ToolCallAccuracy.multi_turn_ascore", 1.0),
    topic=("ragas.metrics.TopicAdherenceScore.multi_turn_ascore", 0.6),
    goal=("ragas.metrics.AgentGoalAccuracyWithoutReference.multi_turn_ascore", 0.85),
)


def _patch_all_realtime(overrides: dict | None = None):
    """Build a dict of {target: AsyncMock} for every realtime metric, with
    optional per-metric overrides (value or an exception instance to raise)."""
    overrides = overrides or {}
    mocks = {}
    for key, (target, default) in REALTIME_METRIC_PATCHES.items():
        override = overrides.get(key)
        if isinstance(override, Exception):
            mocks[target] = AsyncMock(side_effect=override)
        else:
            mocks[target] = AsyncMock(return_value=override if override is not None else default)
    return mocks


def _apply_patches(mocks: dict):
    patchers = [patch(target, new=mock) for target, mock in mocks.items()]
    for p in patchers:
        p.start()
    return patchers


def _stop_patches(patchers: list):
    for p in patchers:
        p.stop()


def _make_case(with_verdict: bool = True):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    inv = Investigation(
        transaction_id="JUDGE-1",
        vendor="Acme Corp",
        category="consulting",
        amount=75000.0,
        materiality=50000.0,
        confidence=0.8,
    )
    session.add(inv)
    session.commit()
    session.refresh(inv)

    evidence = [
        EvidenceArtifact(
            investigation_id=inv.id, source="ledger_row", content="Ledger says X", relevance_score=0.8
        ),
        EvidenceArtifact(
            investigation_id=inv.id, source="policy_kb", content="Policy chunk", relevance_score=0.9
        ),
    ]
    debates = [
        DebateTranscript(
            investigation_id=inv.id, round=1, speaker="challenger", message="Risky because...", token_count=10
        ),
        DebateTranscript(
            investigation_id=inv.id, round=1, speaker="defender", message="Fine because...", token_count=10
        ),
    ]
    if with_verdict:
        debates.append(
            DebateTranscript(
                investigation_id=inv.id,
                round=2,
                speaker="adjudicator",
                message="Verdict: medium risk at 80% confidence.",
                token_count=10,
            )
        )
    session.add_all(evidence + debates)
    session.commit()

    case = rj.ScoredCase(
        investigation=inv,
        evidence=evidence,
        debates=debates,
        scored_provider="anthropic",
        scored_model="claude-sonnet-5",
    )
    return session, case


def test_audit_question_includes_case_facts():
    session, case = _make_case()
    try:
        question = rj._audit_question(case.investigation)
        assert "consulting transaction JUDGE-1" in question
        assert "$75,000.00" in question
        assert "Acme Corp" in question
        assert "$50,000.00" in question
    finally:
        session.close()


def test_verdict_response_picks_latest_adjudicator_message():
    session, case = _make_case()
    try:
        assert rj._verdict_response(case.debates) == "Verdict: medium risk at 80% confidence."
    finally:
        session.close()


def test_verdict_response_is_none_without_adjudicator():
    session, case = _make_case(with_verdict=False)
    try:
        assert rj._verdict_response(case.debates) is None
    finally:
        session.close()


def test_retrieved_contexts_falls_back_when_empty():
    assert rj._retrieved_contexts([]) == ["No evidence was retrieved for this case."]


def test_retrieved_contexts_uses_evidence_content():
    session, case = _make_case()
    try:
        contexts = rj._retrieved_contexts(case.evidence)
        assert contexts == ["Ledger says X", "Policy chunk"]
    finally:
        session.close()


def test_sample_builders_produce_valid_samples():
    session, case = _make_case()
    try:
        single = rj._single_turn_sample(case)
        assert single.response == "Verdict: medium risk at 80% confidence."
        assert single.reference is None
        assert len(single.retrieved_contexts) == 2

        single_with_ref = rj._single_turn_sample(case, reference="Legitimate and authorized.")
        assert single_with_ref.reference == "Legitimate and authorized."

        tool_sample = rj._tool_call_sample(case)
        assert len(tool_sample.user_input) == 2  # human turn + agent turn with tool calls

        topic_sample = rj._topic_sample(case)
        assert topic_sample.reference_topics == rj.AUDIT_TOPICS

        goal_sample = rj._goal_sample(case)
        assert len(goal_sample.user_input) == 1 + len(case.debates)
    finally:
        session.close()


def test_score_realtime_metrics_returns_all_six_keys():
    session, case = _make_case()
    patchers = _apply_patches(_patch_all_realtime())
    try:
        results = asyncio.run(rj.score_realtime_metrics(case))
        assert set(results) == {
            "Faithfulness",
            "Context Precision",
            "Response Relevancy",
            "Tool Call Accuracy",
            "Topic Adherence",
            "Agent Goal Accuracy",
        }
        assert results["Faithfulness"] == 0.9
        assert results["Tool Call Accuracy"] == 1.0
    finally:
        _stop_patches(patchers)
        session.close()


def test_score_realtime_metrics_handles_judge_failure_gracefully():
    """One metric's judge call raising must not affect the others, and must
    surface as None rather than propagating the exception."""
    session, case = _make_case()
    patchers = _apply_patches(_patch_all_realtime({"faithfulness": RuntimeError("judge timed out")}))
    try:
        results = asyncio.run(rj.score_realtime_metrics(case))
        assert results["Faithfulness"] is None
        assert results["Context Precision"] == 0.8
        assert results["Response Relevancy"] == 0.7
    finally:
        _stop_patches(patchers)
        session.close()


def test_score_realtime_metrics_skips_single_turn_when_no_verdict():
    """No adjudicator message -> the 3 single-turn metrics stay None instead
    of being scored against a missing response; the 3 multi-turn metrics
    (which don't depend on a verdict) still score normally."""
    session, case = _make_case(with_verdict=False)
    patchers = _apply_patches(_patch_all_realtime())
    try:
        results = asyncio.run(rj.score_realtime_metrics(case))
        assert results["Faithfulness"] is None
        assert results["Context Precision"] is None
        assert results["Response Relevancy"] is None
        assert results["Tool Call Accuracy"] == 1.0
        assert results["Topic Adherence"] == 0.6
        assert results["Agent Goal Accuracy"] == 0.85
    finally:
        _stop_patches(patchers)
        session.close()


def test_score_reference_metrics_returns_three_keys():
    session, case = _make_case()
    try:
        with patch("ragas.metrics.ContextEntityRecall.single_turn_ascore", new=AsyncMock(return_value=0.6)), patch(
            "ragas.metrics.FactualCorrectness.single_turn_ascore", new=AsyncMock(return_value=0.7)
        ), patch("ragas.metrics.SemanticSimilarity.single_turn_ascore", new=AsyncMock(return_value=0.95)):
            results = asyncio.run(rj.score_reference_metrics(case, reference="Legitimate and authorized."))
        assert set(results) == {"Context Entity Recall", "Factual Correctness", "Semantic Similarity"}
        assert results["Semantic Similarity"] == 0.95
    finally:
        session.close()


def test_score_reference_metrics_handles_judge_failure_gracefully():
    session, case = _make_case()
    try:
        with patch(
            "ragas.metrics.ContextEntityRecall.single_turn_ascore",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ), patch("ragas.metrics.FactualCorrectness.single_turn_ascore", new=AsyncMock(return_value=0.7)), patch(
            "ragas.metrics.SemanticSimilarity.single_turn_ascore", new=AsyncMock(return_value=0.95)
        ):
            results = asyncio.run(rj.score_reference_metrics(case, reference="Legitimate and authorized."))
        assert results["Context Entity Recall"] is None
        assert results["Factual Correctness"] == 0.7
    finally:
        session.close()


def test_judge_available_requires_flag_and_key(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "RAGAS_REALTIME_ENABLED", True)
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-test-key")
    assert rj.judge_available() is True

    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "")
    assert rj.judge_available() is False

    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-test-key")
    monkeypatch.setattr(settings, "RAGAS_REALTIME_ENABLED", False)
    assert rj.judge_available() is False
