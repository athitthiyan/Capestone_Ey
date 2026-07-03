"""
Investigation Executor - orchestrates agent crew execution with real-time
event streaming, state checkpointing, and failure recovery.

The pipeline is a compiled LangGraph ``StateGraph`` (see ``_build_graph``):
evidence -> challenger <-> defender (debate rounds, conditional edge) ->
adjudication -> verification -> either confidence_gate (grounded) or
prepare_retry -> evidence again (ungrounded, retry budget remaining) or
escalate (retry budget exhausted). confidence_gate then routes to either
END (needs human review) or report_and_audit -> END. Both loops - the debate
round loop and the supervisor's verification-retry loop - are native graph
cycles driven by conditional edges, not Python-level for-loops; each debate
round and re-run attempt evolves the transcript instead of repeating it.

The graph is compiled once per executor instance with an in-process
``MemorySaver`` checkpointer, keyed by ``thread_id=investigation_id``. This
gives crash-resume/replay within a single run; it does NOT persist across
process restarts (MemorySaver is in-memory only) - if cross-process resume
is ever needed, swap in a persistent checkpointer (e.g. a Postgres-backed
one) here without touching node logic. This is independent of, and in
addition to, the existing manual checkpoints written to the
`investigation_states` table via `_checkpoint_state` (unchanged, still the
system of record for the audit/timeline UI).

Events are emitted two ways:
  1. Published to Redis (so the FastAPI process can forward them to WebSocket
     clients even though the executor runs inside a Celery worker).
  2. Broadcast to any same-process WebSocket clients (useful in tests / when
     the executor runs inside the API process).
"""

import asyncio
import hashlib
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.agents.crew import InvestigationState as CrewState
from app.core.config import settings
from app.core.metrics import (
    debate_rounds_total,
    investigation_duration_seconds,
    investigations_total,
    verification_results_total,
)
from app.db.models import (
    DebateTranscript,
    EvidenceArtifact,
    Investigation,
    InvestigationState as DBInvestigationState,
    InvestigationStatus,
    ReviewQueueItem,
    RiskLevel,
    ThirdPartyEvidenceVerification,
    VerificationClaim,
)
from app.realtime.websocket_manager import (
    AgentStatusUpdateEvent,
    DebateMessageEvent,
    PipelineStageEvent,
    connection_manager,
)
from app.knowledge.retriever import (
    format_context,
    retrieve_knowledge_context,
    retrieve_knowledge_context_from_db,
)

logger = logging.getLogger(__name__)


def _risk_from_str(value: str) -> RiskLevel:
    try:
        return RiskLevel(str(value).lower())
    except ValueError:
        return RiskLevel.MEDIUM


class GraphState(CrewState, total=False):
    """Runtime state passed between graph nodes.

    Extends app/agents/crew.py's InvestigationState (the fields its
    real-agent node functions read/write: investigation_id, evidence,
    debate_round, ...) with the extra bookkeeping this executor's graph
    control flow needs. Must be a real TypedDict, not a plain dict subclass:
    LangGraph's StateGraph inspects `__annotations__` to determine which
    channels exist, so a schema with no declared keys has nothing to write
    to. No field is `Annotated` with a reducer, so every key gets ordinary
    last-write-wins merge semantics, which is exactly right here since every
    node mutates and returns the same state dict.
    """

    round_cursor: int
    rag_relevance: float
    max_attempts: int
    grounded: bool
    needs_review: bool
    confidence_gate: dict
    outcome: Optional[str]


class InvestigationExecutor:
    """Executes investigations on a compiled LangGraph StateGraph."""

    def __init__(self, db_session: Session):
        self.db = db_session
        self._nodes = None
        self._graph = None

    async def _emit(self, investigation_id: str, event: Dict[str, Any]) -> None:
        try:
            from app.realtime.redis_bus import publish_event

            await asyncio.to_thread(publish_event, investigation_id, event)
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Redis publish skipped: {exc}")
        await connection_manager.broadcast(investigation_id, event)

    def _get_nodes(self) -> dict:
        if self._nodes is None:
            from app.agents.crew import (
                create_adjudicator_agent,
                create_challenger_agent,
                create_defender_agent,
                create_evidence_agent,
                create_verifier_agent,
            )

            self._nodes = {
                "evidence": create_evidence_agent(),
                "challenger": create_challenger_agent(),
                "defender": create_defender_agent(),
                "adjudicator": create_adjudicator_agent(),
                "verifier": create_verifier_agent(),
            }
        return self._nodes

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def _recursion_limit(self, max_attempts: int) -> int:
        # Each debate round is 2 node executions (challenger + defender); each
        # attempt is roughly evidence + 2*max_debate_rounds + adjudication +
        # verification (+ prepare_retry on a retry). Generous headroom over
        # the theoretical max so this is a safety valve, not a real constraint.
        return max(
            50, 10 + max_attempts * (6 + settings.MAX_DEBATE_ROUNDS * 2)
        )

    def _get_graph(self):
        if self._graph is None:
            self._graph = self._build_graph()
        return self._graph

    def _build_graph(self):
        from langgraph.checkpoint.memory import MemorySaver
        from langgraph.graph import END, StateGraph

        from app.agents.crew import route_debate

        graph = StateGraph(GraphState)

        # Node names must not collide with GraphState field names (LangGraph
        # rejects that), hence collect_evidence/adjudicate/confidence_routing
        # rather than evidence/adjudication/confidence_gate - those are the
        # state keys the nodes themselves read and write.
        graph.add_node("collect_evidence", self._node_evidence)
        graph.add_node("challenger", self._node_challenger)
        graph.add_node("defender", self._node_defender)
        graph.add_node("adjudicate", self._node_adjudication)
        graph.add_node("verification", self._node_verification)
        graph.add_node("prepare_retry", self._node_prepare_retry)
        graph.add_node("escalate", self._node_escalate)
        graph.add_node("confidence_routing", self._node_confidence_gate)
        graph.add_node("report_and_audit", self._node_report_and_audit)

        graph.set_entry_point("collect_evidence")
        graph.add_edge("collect_evidence", "challenger")
        graph.add_edge("challenger", "defender")
        graph.add_conditional_edges(
            "defender",
            route_debate,
            {"challenger": "challenger", "adjudicator": "adjudicate"},
        )
        graph.add_edge("adjudicate", "verification")
        graph.add_conditional_edges(
            "verification",
            self._route_after_verification,
            {
                "confidence_gate": "confidence_routing",
                "prepare_retry": "prepare_retry",
                "escalate": "escalate",
            },
        )
        graph.add_edge("prepare_retry", "collect_evidence")
        graph.add_edge("escalate", END)
        graph.add_conditional_edges(
            "confidence_routing",
            self._route_after_confidence_gate,
            {"review": END, "report": "report_and_audit"},
        )
        graph.add_edge("report_and_audit", END)

        return graph.compile(checkpointer=MemorySaver())

    # ------------------------------------------------------------------
    # Routing (conditional edges) - pure functions of state, no side effects
    # ------------------------------------------------------------------

    def _route_after_verification(self, state: dict) -> str:
        if state.get("grounded"):
            return "confidence_gate"
        if state.get("attempt", 1) < state.get("max_attempts", 1):
            return "prepare_retry"
        return "escalate"

    def _route_after_confidence_gate(self, state: dict) -> str:
        return "review" if state.get("needs_review") else "report"

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    async def execute_investigation(self, investigation_id: str) -> Dict[str, Any]:
        logger.info(f"Starting investigation execution: {investigation_id}")
        started = time.perf_counter()
        result_status = "failed"
        try:
            investigation = self.db.get(Investigation, investigation_id)
            if not investigation:
                raise ValueError(f"Investigation {investigation_id} not found")

            self._reset_generated_outputs(investigation_id)
            state = self._initialize_state(investigation)

            await self._emit(
                investigation_id,
                AgentStatusUpdateEvent(
                    investigation_id=investigation_id,
                    agent="supervisor",
                    state="running",
                    message="Investigation started",
                ).to_dict(),
            )

            graph = self._get_graph()
            final_state = await graph.ainvoke(
                state,
                config={
                    "configurable": {"thread_id": investigation_id},
                    "recursion_limit": self._recursion_limit(state["max_attempts"]),
                },
            )

            outcome = final_state.get("outcome")

            if outcome == "escalated":
                result_status = "escalated"
                return {
                    "status": "escalated",
                    "investigation_id": investigation_id,
                    "reason": "verdict could not be grounded within the retry budget",
                }

            if outcome == "review":
                result_status = "review"
                return {
                    "status": "review",
                    "investigation_id": investigation_id,
                    "risk": final_state.get("adjudication", {}).get("risk_level", "unknown"),
                    "confidence": final_state.get("adjudication", {}).get("confidence", 0),
                    "attempts": final_state.get("attempt", 1),
                }

            if outcome == "completed":
                logger.info(f"Investigation {investigation_id} completed")
                result_status = "completed"
                return {
                    "status": "completed",
                    "investigation_id": investigation_id,
                    "risk": final_state.get("adjudication", {}).get("risk_level", "unknown"),
                    "confidence": final_state.get("adjudication", {}).get("confidence", 0),
                    "attempts": final_state.get("attempt", 1),
                }

            # Defensive: the graph should always set one of the three outcomes
            # above before reaching END. If it didn't, treat it as a failure
            # rather than silently returning an ambiguous result.
            raise RuntimeError(
                f"Investigation graph ended without a recognized outcome: {final_state!r}"
            )

        except Exception as e:  # noqa: BLE001
            logger.error(f"Investigation {investigation_id} failed: {e}", exc_info=True)
            await self._emit(
                investigation_id,
                AgentStatusUpdateEvent(
                    investigation_id=investigation_id,
                    agent="supervisor",
                    state="failed",
                    message=f"Error: {e}",
                ).to_dict(),
            )
            self.db.rollback()
            investigation = self.db.get(Investigation, investigation_id)
            if investigation:
                investigation.status = InvestigationStatus.FAILED
                investigation.error_message = str(e)[:2000]
                self.db.commit()
            return {"status": "failed", "investigation_id": investigation_id, "error": str(e)}

        finally:
            investigations_total.labels(status=result_status).inc()
            investigation_duration_seconds.observe(time.perf_counter() - started)

    def _initialize_state(self, investigation: Investigation) -> dict:
        return GraphState(
            investigation_id=investigation.id,
            transaction_id=investigation.transaction_id,
            vendor=investigation.vendor,
            category=investigation.category,
            amount=investigation.amount,
            materiality=investigation.materiality,
            evidence=[],
            evidence_summary="",
            debate_round=0,
            round_cursor=0,
            attempt=1,
            max_attempts=settings.MAX_VERIFICATION_RETRIES + 1,
            has_corroboration=False,
            verification_feedback="",
            max_debate_rounds=settings.MAX_DEBATE_ROUNDS,
            challenger_arguments=[],
            defender_arguments=[],
            debate_transcript=[],
            adjudication={},
            verification_results={},
            rag_context="",
            rag_citations=[],
            rag_relevance=0.0,
            messages=[],
            llm_usage=[],
            workflow_state="intake",
            status="running",
            grounded=False,
            needs_review=False,
            confidence_gate={},
            outcome=None,
        )

    def _reset_generated_outputs(self, investigation_id: str) -> None:
        """Keep re-runs idempotent by replacing generated investigation outputs."""
        for model in (EvidenceArtifact, DebateTranscript, VerificationClaim, DBInvestigationState):
            self.db.query(model).filter(model.investigation_id == investigation_id).delete(
                synchronize_session=False
            )
        self.db.query(ReviewQueueItem).filter(
            ReviewQueueItem.investigation_id == investigation_id,
            ReviewQueueItem.status == "pending",
        ).update(
            {
                ReviewQueueItem.status: "superseded",
                ReviewQueueItem.completed_at: datetime.utcnow(),
            },
            synchronize_session=False,
        )
        self.db.commit()

    async def _write_audit(
        self,
        investigation_id: str,
        event: str,
        actor: str,
        details: dict[str, Any],
    ) -> None:
        try:
            from app.audit import eventstore

            handlers = {
                "evidence_collected": eventstore.log_evidence_collected,
                "debate_started": eventstore.log_debate_started,
                "debate_round_completed": eventstore.log_debate_round_completed,
                "adjudication_completed": eventstore.log_adjudication_completed,
                "verification_completed": eventstore.log_verification_completed,
            }
            handler = handlers.get(event)
            if handler:
                await handler(investigation_id, actor=actor, details=details)
            else:
                await eventstore._log(event, investigation_id, actor, details)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Audit log write failed for {event}: {exc}")

    def _set_status(self, investigation_id: str, status: InvestigationStatus) -> None:
        investigation = self.db.get(Investigation, investigation_id)
        if investigation:
            investigation.status = status
            self.db.commit()

    # ------------------------------------------------------------------
    # Graph nodes
    # ------------------------------------------------------------------

    async def _node_evidence(self, state: dict) -> dict:
        investigation_id = state["investigation_id"]
        # Fresh debate-round budget for this attempt - _route_debate uses this
        # to run exactly max_debate_rounds full rounds before adjudication.
        state["debate_round"] = 0

        attempt = state.get("attempt", 1)
        logger.info(f"Evidence collection phase (attempt {attempt}): {investigation_id}")
        self._set_status(investigation_id, InvestigationStatus.COLLECTING_EVIDENCE)

        await self._emit(
            investigation_id,
            PipelineStageEvent(investigation_id, "intake", "collecting_evidence").to_dict(),
        )
        await self._emit(
            investigation_id,
            AgentStatusUpdateEvent(
                investigation_id,
                "evidence_agent",
                "running",
                "Re-querying for external corroboration..."
                if attempt > 1
                else "Collecting evidence...",
            ).to_dict(),
        )

        query = " ".join(
            [
                str(state.get("vendor", "")),
                str(state.get("category", "")),
                str(state.get("amount", "")),
                str(state.get("verification_feedback", "")),
                "materiality approval vendor policy expense evidence",
            ]
        )
        try:
            policy_chunks = retrieve_knowledge_context_from_db(self.db, query, limit=4)
        except Exception as exc:  # noqa: BLE001
            logger.warning("DB-backed RAG retrieval failed; using corpus fallback: %s", exc)
            policy_chunks = retrieve_knowledge_context(query, limit=4)
        state["rag_context"] = format_context(policy_chunks)
        state["rag_citations"] = [chunk["id"] for chunk in policy_chunks]
        # Mean of the retriever's own per-chunk relevance, so the evidence
        # artifact's relevance_score (and therefore RAGAS Context Precision)
        # reflects this call's actual retrieval quality instead of a constant.
        state["rag_relevance"] = (
            round(sum(c.get("relevance", 0.0) for c in policy_chunks) / len(policy_chunks), 4)
            if policy_chunks
            else 0.0
        )

        new_items: list[dict] = []
        if settings.USE_REAL_AGENTS:
            # Real retrieval: re-invoking the node issues a fresh (feedback-aware)
            # query, which can surface evidence the first pass did not retrieve.
            previous_count = len(state.get("evidence", []))
            state.update(await asyncio.to_thread(self._get_nodes()["evidence"], state))
            new_items = state.get("evidence", [])[previous_count:]
        elif attempt == 1:
            await asyncio.sleep(0.2)
            state["evidence_summary"] = (
                f"Ledger transaction {state['transaction_id']} for {state['vendor']} "
                f"was posted to {state['category']} for {state['amount']:.2f}. "
                f"Retrieved {len(policy_chunks)} policy/data chunks from the knowledge base."
            )
            new_items = [
                {
                    "source": "ledger_row",
                    "content": (
                        f"Transaction {state['transaction_id']} records vendor {state['vendor']} "
                        f"in account/category {state['category']} with amount {state['amount']:.2f}."
                    ),
                    "citations": [f"ledger:{state['transaction_id']}"],
                    "relevance_score": 0.8,
                },
                {
                    "source": "intake_prefilter",
                    "content": (
                        f"Materiality threshold is {state['materiality']:.2f}; "
                        f"the transaction amount is {state['amount']:.2f}."
                    ),
                    "citations": ["deterministic-intake-rules"],
                    "relevance_score": 0.68,
                },
            ]
            if policy_chunks:
                new_items.append(
                    {
                        "source": "policy_kb",
                        "content": state["rag_context"],
                        "citations": state["rag_citations"],
                        # Real per-query retrieval relevance (see rag_relevance
                        # above), not a fixed constant - varies with how well
                        # the corpus actually matches this transaction.
                        "relevance_score": state["rag_relevance"],
                    }
                )
            state["evidence"] = list(new_items)
        else:
            # Re-run: the Supervisor sent the case back for corroboration. A
            # refined query to the vendor registry surfaces external support
            # that the first, narrower retrieval missed.
            await asyncio.sleep(0.1)
            corroboration = {
                "source": "vendor_registry",
                "content": (
                    f"External corroboration: {state['vendor']} is a registered, approved "
                    f"supplier with master-data on file and a matching purchase order / "
                    f"delegated-authority approval covering {state['amount']:.2f}."
                ),
                "citations": [f"registry:{state['vendor'].lower().replace(' ', '-')}"],
                "relevance_score": 0.86,
            }
            new_items = [corroboration]
            state.setdefault("evidence", []).append(corroboration)
            state["evidence_summary"] = (
                state.get("evidence_summary", "")
                + " External corroboration retrieved from the vendor registry."
            )
            state["has_corroboration"] = True

        for item in new_items:
            self.db.add(
                EvidenceArtifact(
                    investigation_id=investigation_id,
                    source=item.get("source", "agent"),
                    content=item.get("content", ""),
                    citations=item.get("citations", []),
                    relevance_score=float(item.get("relevance_score", 0) or 0),
                )
            )
        self.db.commit()
        await self._write_audit(
            investigation_id,
            "evidence_collected",
            actor="evidence_agent",
            details={"evidence_count": len(state.get("evidence", [])), "attempt": attempt},
        )

        await self._emit(
            investigation_id,
            AgentStatusUpdateEvent(
                investigation_id,
                "evidence_agent",
                "done",
                "Corroboration retrieved" if attempt > 1 else "Evidence collected",
                metadata={"evidence_count": len(state.get("evidence", []))},
            ).to_dict(),
        )
        self._checkpoint_state(investigation_id, f"evidence_collection_{attempt}", state)
        return state

    # --- deterministic stub argument generators (USE_REAL_AGENTS=false) ---

    def _stub_challenger(self, state: dict, round_num: int) -> str:
        amount = float(state.get("amount") or 0)
        materiality = float(state.get("materiality") or settings.DEFAULT_MATERIALITY_THRESHOLD)
        if state.get("has_corroboration"):
            return (
                f"Round {round_num}: the vendor registry now corroborates the supplier, but the "
                f"{amount:.2f} amount still sits above the materiality threshold of {materiality:.2f}; "
                f"I accept the approval evidence yet maintain this warranted scrutiny."
            )
        if state.get("defender_arguments"):
            return (
                f"Round {round_num}: the Defender calls the evidence limited - exactly my point. "
                f"Without external corroboration, the {amount:.2f} overage above {materiality:.2f} "
                f"is an unmitigated control risk, not a minor exception."
            )
        return (
            f"Round {round_num}: {state['vendor']} transaction {state['transaction_id']} exceeds "
            f"materiality ({amount:.2f} vs {materiality:.2f}); absent corroborating approval this is "
            f"a control risk that should be challenged."
        )

    def _stub_defender(self, state: dict, round_num: int) -> str:
        amount = float(state.get("amount") or 0)
        materiality = float(state.get("materiality") or settings.DEFAULT_MATERIALITY_THRESHOLD)
        if state.get("has_corroboration"):
            return (
                f"Round {round_num}: the vendor registry confirms an approved, registered supplier "
                f"with a purchase order and delegated-authority approval on file - the {amount:.2f} "
                f"transaction is corroborated and within policy."
            )
        return (
            f"Round {round_num}: evidence is currently limited to ledger metadata and intake rules; "
            f"pending external corroboration, the {amount:.2f} overage over {materiality:.2f} is "
            f"small and fully traceable to the ledger row."
        )

    async def _node_challenger(self, state: dict) -> dict:
        investigation_id = state["investigation_id"]
        attempt = state.get("attempt", 1)

        if state.get("debate_round", 0) == 0:
            # First round of this attempt - transition the pipeline stage and
            # write the one-time "debate started" audit event.
            logger.info(f"Debate phase (attempt {attempt}): {investigation_id}")
            self._set_status(investigation_id, InvestigationStatus.AGENT_DEBATE)
            await self._emit(
                investigation_id,
                PipelineStageEvent(
                    investigation_id, "collecting_evidence", "agent_debate"
                ).to_dict(),
            )
            await self._write_audit(
                investigation_id,
                "debate_started",
                actor="supervisor",
                details={"max_rounds": settings.MAX_DEBATE_ROUNDS, "attempt": attempt},
            )

        nodes = self._get_nodes() if settings.USE_REAL_AGENTS else None

        state["round_cursor"] = state.get("round_cursor", 0) + 1
        round_num = state["round_cursor"]
        debate_rounds_total.inc()

        await self._emit(
            investigation_id,
            AgentStatusUpdateEvent(
                investigation_id, "challenger", "running",
                f"Round {round_num}: presenting risk analysis...",
            ).to_dict(),
        )
        if nodes:
            state.update(await asyncio.to_thread(nodes["challenger"], state))
            challenger_msg = state["challenger_arguments"][-1]
        else:
            await asyncio.sleep(0.05)
            challenger_msg = self._stub_challenger(state, round_num)
            state.setdefault("challenger_arguments", []).append(challenger_msg)

        self.db.add(
            DebateTranscript(
                investigation_id=investigation_id,
                round=round_num,
                speaker="challenger",
                message=challenger_msg,
                token_count=len(challenger_msg.split()),
            )
        )
        self.db.commit()
        await self._emit(
            investigation_id,
            DebateMessageEvent(investigation_id, round_num, "challenger", challenger_msg).to_dict(),
        )
        return state

    async def _node_defender(self, state: dict) -> dict:
        investigation_id = state["investigation_id"]
        round_num = state["round_cursor"]
        nodes = self._get_nodes() if settings.USE_REAL_AGENTS else None

        await self._emit(
            investigation_id,
            AgentStatusUpdateEvent(
                investigation_id, "defender", "running",
                f"Round {round_num}: presenting supporting evidence...",
            ).to_dict(),
        )
        if nodes:
            state.update(await asyncio.to_thread(nodes["defender"], state))
            defender_msg = state["defender_arguments"][-1]
            # crew.py's real defender_node already increments debate_round.
        else:
            await asyncio.sleep(0.05)
            defender_msg = self._stub_defender(state, round_num)
            state.setdefault("defender_arguments", []).append(defender_msg)
            state["debate_round"] = state.get("debate_round", 0) + 1

        self.db.add(
            DebateTranscript(
                investigation_id=investigation_id,
                round=round_num,
                speaker="defender",
                message=defender_msg,
                token_count=len(defender_msg.split()),
            )
        )
        self.db.commit()
        await self._emit(
            investigation_id,
            DebateMessageEvent(investigation_id, round_num, "defender", defender_msg).to_dict(),
        )
        await self._write_audit(
            investigation_id,
            "debate_round_completed",
            actor="agent_crew",
            details={"round": round_num, "messages": 2},
        )

        if state.get("debate_round", 0) >= settings.MAX_DEBATE_ROUNDS:
            self._checkpoint_state(
                investigation_id, f"debate_{state.get('attempt', 1)}", state
            )
        return state

    async def _node_adjudication(self, state: dict) -> dict:
        investigation_id = state["investigation_id"]
        logger.info(f"Adjudication phase: {investigation_id}")
        await self._emit(
            investigation_id,
            AgentStatusUpdateEvent(
                investigation_id, "adjudicator", "running", "Weighing debate arguments..."
            ).to_dict(),
        )

        if settings.USE_REAL_AGENTS:
            state.update(await asyncio.to_thread(self._get_nodes()["adjudicator"], state))
            adjudication = state.get("adjudication", {})
        else:
            await asyncio.sleep(0.1)
            amount = float(state.get("amount") or 0)
            materiality = float(state.get("materiality") or settings.DEFAULT_MATERIALITY_THRESHOLD)
            corroborated = bool(state.get("has_corroboration"))
            if amount >= materiality:
                risk_level = "medium" if corroborated else "high"
                confidence = 0.92 if corroborated else 0.78
            elif amount >= materiality * 0.5:
                risk_level = "medium"
                confidence = 0.74 if corroborated else 0.7
            else:
                risk_level = "low"
                confidence = 0.66 if corroborated else 0.62
            adjudication = {
                "risk_level": risk_level,
                "confidence": confidence,
                "reasoning": (
                    f"Deterministic local analysis compared the transaction amount ({amount:.2f}) "
                    f"with materiality ({materiality:.2f}) and weighed the debate"
                    + (
                        " together with the external corroboration retrieved on re-run."
                        if corroborated
                        else ", which lacked external corroboration."
                    )
                ),
                "key_concerns": (
                    ["Requires reviewer confirmation before partner sign-off"]
                    if corroborated
                    else [
                        "Ledger-only evidence set",
                        "No external corroboration for the materiality overage",
                    ]
                ),
                "mitigating_factors": (
                    [
                        "Vendor registry confirms an approved supplier with PO on file",
                        "Transaction is traceable to the uploaded ledger row",
                    ]
                    if corroborated
                    else ["Transaction is traceable to the uploaded ledger row"]
                ),
            }
            state["adjudication"] = adjudication

        risk_level = adjudication.get("risk_level", "medium")
        # A malformed LLM JSON response (e.g. confidence: 150) must not leak an
        # out-of-range value into the confidence-gate thresholds below.
        confidence = max(0.0, min(1.0, float(adjudication.get("confidence", 0.5) or 0.5)))

        investigation = self.db.get(Investigation, investigation_id)
        investigation.risk = _risk_from_str(risk_level)
        investigation.confidence = confidence
        self.db.commit()

        # Record the verdict in the transcript so it shows in the Adjudicator
        # column of the debate viewer (with its confidence).
        verdict_msg = (
            f"Verdict: {risk_level} risk at {confidence * 100:.0f}% confidence. "
            f"{adjudication.get('reasoning', '')}"
        )
        self.db.add(
            DebateTranscript(
                investigation_id=investigation_id,
                round=state.get("round_cursor", settings.MAX_DEBATE_ROUNDS),
                speaker="adjudicator",
                message=verdict_msg,
                token_count=len(verdict_msg.split()),
            )
        )
        self.db.commit()

        await self._emit(
            investigation_id,
            DebateMessageEvent(
                investigation_id,
                state.get("round_cursor", settings.MAX_DEBATE_ROUNDS),
                "adjudicator",
                verdict_msg,
            ).to_dict(),
        )
        await self._emit(
            investigation_id,
            AgentStatusUpdateEvent(
                investigation_id,
                "adjudicator",
                "done",
                f"Verdict: {risk_level} risk (confidence: {confidence})",
                metadata={
                    "risk_level": risk_level,
                    "confidence": confidence,
                    "key_concerns": adjudication.get("key_concerns", []),
                },
            ).to_dict(),
        )
        await self._write_audit(
            investigation_id,
            "adjudication_completed",
            actor="adjudicator",
            details={"risk": risk_level, "confidence": confidence},
        )
        self._checkpoint_state(investigation_id, f"adjudication_{state.get('attempt', 1)}", state)
        return state

    async def _node_verification(self, state: dict) -> dict:
        """Run the Verifier and record whether the verdict is grounded."""
        investigation_id = state["investigation_id"]
        logger.info(f"Verification phase: {investigation_id}")
        self._set_status(investigation_id, InvestigationStatus.VERIFICATION)

        await self._emit(
            investigation_id,
            PipelineStageEvent(investigation_id, "agent_debate", "verification").to_dict(),
        )
        await self._emit(
            investigation_id,
            AgentStatusUpdateEvent(
                investigation_id, "verifier", "running", "Verifying claims..."
            ).to_dict(),
        )

        if settings.USE_REAL_AGENTS:
            state.update(await asyncio.to_thread(self._get_nodes()["verifier"], state))
            verification = state.get("verification_results", {})
        else:
            await asyncio.sleep(0.05)
            amount = float(state.get("amount") or 0)
            materiality = float(state.get("materiality") or settings.DEFAULT_MATERIALITY_THRESHOLD)
            over_materiality = amount >= materiality
            has_corroboration = bool(state.get("has_corroboration"))
            # A high-risk overage with only internal (ledger/intake) evidence is
            # not yet grounded - the Verifier sends it back for corroboration.
            is_grounded = (not over_materiality) or has_corroboration
            if is_grounded:
                verification = {
                    "is_grounded": True,
                    "ungrounded_claims": [],
                    "verification_report": (
                        "All material claims are grounded in the available evidence"
                        + (
                            " including the external corroboration retrieved on re-run."
                            if has_corroboration
                            else " (transaction is within materiality)."
                        )
                    ),
                }
            else:
                verification = {
                    "is_grounded": False,
                    "ungrounded_claims": [
                        "The elevated-risk verdict relies on a materiality overage that has no "
                        "external corroboration in the current evidence set."
                    ],
                    "verification_report": (
                        "Verdict not fully grounded: external corroboration for the materiality "
                        "overage is missing. Recommend re-querying corroborating sources."
                    ),
                }
            state["verification_results"] = verification

        is_grounded = bool(verification.get("is_grounded", True))
        state["grounded"] = is_grounded
        verification_results_total.labels(grounded=str(is_grounded).lower()).inc()
        adjudication = state.get("adjudication", {})
        self.db.add(
            VerificationClaim(
                investigation_id=investigation_id,
                claim_text=f"Risk assessment: {adjudication.get('risk_level', 'unknown')}",
                is_grounded=is_grounded,
                explanation=verification.get("verification_report"),
                supporting_evidence=[
                    item.get("source", "evidence")
                    for item in state.get("evidence", [])
                    if isinstance(item, dict)
                ],
            )
        )
        self.db.commit()

        await self._emit(
            investigation_id,
            AgentStatusUpdateEvent(
                investigation_id,
                "verifier",
                "done" if is_grounded else "failed",
                "All claims verified and grounded"
                if is_grounded
                else "Ungrounded claims found - returning to Supervisor",
                metadata={
                    "is_grounded": is_grounded,
                    "ungrounded_claims": verification.get("ungrounded_claims", []),
                },
            ).to_dict(),
        )
        await self._write_audit(
            investigation_id,
            "verification_completed",
            actor="verifier",
            details={"is_grounded": is_grounded},
        )
        self._checkpoint_state(investigation_id, f"verification_{state.get('attempt', 1)}", state)
        return state

    async def _node_prepare_retry(self, state: dict) -> dict:
        """Verifier rejected the verdict and retry budget remains - loop back
        to evidence collection with feedback about what needs corroboration."""
        investigation_id = state["investigation_id"]
        attempt = state.get("attempt", 1)
        max_attempts = state.get("max_attempts", 1)
        feedback = "; ".join(
            state.get("verification_results", {}).get("ungrounded_claims", [])
        )
        state["verification_feedback"] = feedback
        next_attempt = attempt + 1

        await self._emit(
            investigation_id,
            AgentStatusUpdateEvent(
                investigation_id,
                "supervisor",
                "retry",
                f"Verification ungrounded - re-running with a corroboration "
                f"query (attempt {next_attempt} of {max_attempts})",
                metadata={"attempt": next_attempt, "feedback": feedback},
            ).to_dict(),
        )
        state["attempt"] = next_attempt
        return state

    def _latest_third_party_verification(
        self,
        investigation_id: str,
    ) -> ThirdPartyEvidenceVerification | None:
        return (
            self.db.query(ThirdPartyEvidenceVerification)
            .filter(ThirdPartyEvidenceVerification.claim_id == investigation_id)
            .order_by(ThirdPartyEvidenceVerification.created_at.desc())
            .first()
        )

    def _review_queue_for(self, risk: RiskLevel, confidence: float) -> tuple[str, str, int]:
        if risk == RiskLevel.CRITICAL or confidence < settings.DEFAULT_ESCALATION_THRESHOLD:
            return ("partner", "engagement_partner", 1)
        return ("reviewer", "reviewer_pool", 2 if risk == RiskLevel.HIGH else 3)

    def _upsert_review_queue(
        self,
        investigation_id: str,
        assigned_to: str,
        priority: int,
        notes: str,
    ) -> ReviewQueueItem:
        row = (
            self.db.query(ReviewQueueItem)
            .filter(
                ReviewQueueItem.investigation_id == investigation_id,
                ReviewQueueItem.status == "pending",
            )
            .order_by(ReviewQueueItem.created_at.desc())
            .first()
        )
        if row is None:
            row = ReviewQueueItem(investigation_id=investigation_id)
            self.db.add(row)

        row.assigned_to = assigned_to
        row.priority = priority
        row.status = "pending"
        row.notes = notes
        row.completed_at = None
        row.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(row)
        return row

    async def _node_confidence_gate(self, state: dict) -> dict:
        """Route grounded cases either to report generation or human review."""
        investigation_id = state["investigation_id"]
        logger.info(f"Confidence gate phase: {investigation_id}")
        investigation = self.db.get(Investigation, investigation_id)
        risk = investigation.risk or RiskLevel.MEDIUM
        confidence = float(investigation.confidence or 0)
        third_party = self._latest_third_party_verification(investigation_id)
        third_party_status = third_party.verification_status if third_party else "NOT_RUN"
        third_party_needs_review = third_party_status in {
            "FLAGGED",
            "API_UNAVAILABLE",
            "NEEDS_MANUAL_REVIEW",
            "NOT_RUN",
        }
        risk_needs_review = risk in {RiskLevel.CRITICAL, RiskLevel.HIGH, RiskLevel.MEDIUM}
        confidence_needs_review = confidence < settings.DEFAULT_CONFIDENCE_THRESHOLD
        needs_review = risk_needs_review or confidence_needs_review or third_party_needs_review

        gate = {
            "risk": risk.value if hasattr(risk, "value") else str(risk),
            "confidence": confidence,
            "confidence_threshold": settings.DEFAULT_CONFIDENCE_THRESHOLD,
            "escalation_threshold": settings.DEFAULT_ESCALATION_THRESHOLD,
            "third_party_status": third_party_status,
            "decision": "human_review" if needs_review else "report_ready",
            "reasons": [
                reason
                for reason, active in [
                    (f"risk is {risk.value}", risk_needs_review),
                    (
                        f"confidence {confidence:.2f} is below {settings.DEFAULT_CONFIDENCE_THRESHOLD:.2f}",
                        confidence_needs_review,
                    ),
                    (
                        f"third-party evidence status is {third_party_status}",
                        third_party_needs_review,
                    ),
                ]
                if active
            ],
        }
        state["confidence_gate"] = gate
        state["needs_review"] = needs_review

        await self._emit(
            investigation_id,
            PipelineStageEvent(investigation_id, "verification", "confidence_gate").to_dict(),
        )
        await self._emit(
            investigation_id,
            AgentStatusUpdateEvent(
                investigation_id,
                "confidence_gate",
                "running",
                "Applying confidence, risk, and third-party evidence routing rules.",
                metadata=gate,
            ).to_dict(),
        )

        if needs_review:
            queue_name, assigned_to, priority = self._review_queue_for(risk, confidence)
            notes = "; ".join(gate["reasons"]) or "Confidence gate routed case to review."
            review_item = self._upsert_review_queue(
                investigation_id,
                assigned_to=assigned_to,
                priority=priority,
                notes=notes,
            )
            investigation.status = InvestigationStatus.HUMAN_REVIEW
            investigation.reviewer = assigned_to
            self.db.commit()

            gate.update(
                {
                    "queue": queue_name,
                    "assigned_to": assigned_to,
                    "priority": priority,
                    "review_queue_item_id": review_item.id,
                }
            )
            state["outcome"] = "review"
            await self._emit(
                investigation_id,
                PipelineStageEvent(investigation_id, "confidence_gate", "human_review").to_dict(),
            )
            await self._emit(
                investigation_id,
                AgentStatusUpdateEvent(
                    investigation_id,
                    "confidence_gate",
                    "review",
                    f"Assigned to {assigned_to} in the {queue_name} queue.",
                    metadata=gate,
                ).to_dict(),
            )
        else:
            await self._emit(
                investigation_id,
                PipelineStageEvent(investigation_id, "confidence_gate", "report_ready").to_dict(),
            )
            await self._emit(
                investigation_id,
                AgentStatusUpdateEvent(
                    investigation_id,
                    "confidence_gate",
                    "done",
                    "Confidence gate cleared case for report generation.",
                    metadata=gate,
                ).to_dict(),
            )

        await self._write_audit(
            investigation_id,
            "confidence_gate_completed",
            actor="confidence_gate",
            details=gate,
        )
        self._checkpoint_state(investigation_id, "confidence_gate", state)
        return state

    async def _node_escalate(self, state: dict) -> dict:
        """Retry budget exhausted - hand the case to a human reviewer."""
        investigation_id = state["investigation_id"]
        logger.info(f"Escalation phase: {investigation_id}")
        investigation = self.db.get(Investigation, investigation_id)
        investigation.status = InvestigationStatus.HUMAN_REVIEW
        investigation.reviewer = "engagement_partner"
        self._upsert_review_queue(
            investigation_id,
            assigned_to="engagement_partner",
            priority=1,
            notes="Verifier could not ground the verdict within retry budget.",
        )
        self.db.commit()

        attempts = state.get("attempt", 1)
        await self._emit(
            investigation_id,
            PipelineStageEvent(investigation_id, "verification", "human_review").to_dict(),
        )
        await self._emit(
            investigation_id,
            AgentStatusUpdateEvent(
                investigation_id,
                "supervisor",
                "escalated",
                f"Could not ground the verdict after {attempts} attempt(s) - "
                f"escalated to human review.",
                metadata={"attempts": attempts},
            ).to_dict(),
        )
        self._checkpoint_state(investigation_id, "escalation", state)
        state["outcome"] = "escalated"
        return state

    async def _node_report_and_audit(self, state: dict) -> dict:
        investigation_id = state["investigation_id"]
        logger.info(f"Report & audit phase: {investigation_id}")
        investigation = self.db.get(Investigation, investigation_id)
        investigation.status = InvestigationStatus.REPORT_READY
        investigation.completed_at = datetime.utcnow()
        self.db.commit()

        try:
            from app.audit.eventstore import log_case_closed

            await log_case_closed(
                investigation_id,
                actor="system",
                details={
                    "risk": investigation.risk.value if investigation.risk else None,
                    "confidence": investigation.confidence,
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Audit log write failed: {exc}")

        await self._emit(
            investigation_id,
            PipelineStageEvent(investigation_id, "confidence_gate", "report_ready").to_dict(),
        )
        await self._emit(
            investigation_id,
            AgentStatusUpdateEvent(
                investigation_id,
                "supervisor",
                "done",
                "Investigation complete - report generated",
                metadata={
                    "risk": investigation.risk.value if investigation.risk else None,
                    "confidence": investigation.confidence,
                },
            ).to_dict(),
        )
        self._checkpoint_state(investigation_id, "report_and_audit", state)
        state["outcome"] = "completed"
        return state

    def _checkpoint_state(self, investigation_id: str, phase: str, state: dict) -> None:
        state_json = json.loads(json.dumps(dict(state), default=str))
        state_hash = hashlib.sha256(
            json.dumps(state_json, sort_keys=True).encode()
        ).hexdigest()

        self.db.add(
            DBInvestigationState(
                investigation_id=investigation_id,
                phase=phase,
                state_json=state_json,
                checkpoint_hash=state_hash,
            )
        )
        self.db.commit()
        logger.info(f"Checkpoint saved for {investigation_id} phase {phase}")
