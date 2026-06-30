"""Knowledge-base routes - policy sources backing the Evidence agent's RAG."""

from fastapi import APIRouter, Depends

from app.core.security import get_current_user

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

# Curated catalog of the policy sources the Evidence agent retrieves over. This
# is configuration-style reference data (not per-investigation telemetry); a real
# deployment would back it with the embedding store's collection metadata.
_SOURCES = [
    {
        "id": "kb-approval-matrix",
        "title": "Delegated Approval Matrix",
        "description": "Spend authority limits by role, entity, and account class.",
        "owner": "Controllership",
        "count": "126 clauses",
        "freshness": "Updated 4 days ago",
        "status": "synced",
        "clause_preview": "Payments above 25,000 require dual sign-off by a controller and partner.",
        "version_history": ["v4.2 (current)", "v4.1", "v4.0"],
        "citation_ids": ["approval-matrix-4.2", "approval-matrix-4.1"],
        "embedding_status": "indexed",
    },
    {
        "id": "kb-related-party",
        "title": "Related-Party Transaction Policy",
        "description": "Identification, disclosure, and approval rules for related parties.",
        "owner": "Risk & Compliance",
        "count": "58 clauses",
        "freshness": "Updated 2 weeks ago",
        "status": "synced",
        "clause_preview": "Transactions with entities sharing common ownership must be flagged and disclosed.",
        "version_history": ["v3.0 (current)", "v2.6"],
        "citation_ids": ["related-party-3.0"],
        "embedding_status": "indexed",
    },
    {
        "id": "kb-vendor-master",
        "title": "Vendor Master & Onboarding SOP",
        "description": "Supplier registration, bank-detail verification, and master-data controls.",
        "owner": "Procurement",
        "count": "91 clauses",
        "freshness": "Updated 9 days ago",
        "status": "review_needed",
        "clause_preview": "New suppliers require tax-ID validation and an approved purchase order before payment.",
        "version_history": ["v2.3 (current)", "v2.2", "v2.1"],
        "citation_ids": ["vendor-master-2.3"],
        "embedding_status": "indexed",
    },
    {
        "id": "kb-fx-rates",
        "title": "FX Rate Reference (Frankfurter)",
        "description": "Daily foreign-exchange rates used to normalise multi-currency ledgers.",
        "owner": "Treasury",
        "count": "Daily feed",
        "freshness": "Synced today",
        "status": "synced",
        "clause_preview": "Rates are cached daily with a fallback to the last known good snapshot.",
        "version_history": ["live feed"],
        "citation_ids": ["fx-frankfurter"],
        "embedding_status": "indexed",
    },
    {
        "id": "kb-expense-sop",
        "title": "Expense Recognition SOP",
        "description": "Capitalisation thresholds and account-mapping rules for expenses.",
        "owner": "Controllership",
        "count": "73 clauses",
        "freshness": "Updated 6 weeks ago",
        "status": "stale",
        "clause_preview": "Consulting spend is recognised in the period the service is rendered.",
        "version_history": ["v1.8 (current)", "v1.7"],
        "citation_ids": ["expense-sop-1.8"],
        "embedding_status": "indexing",
    },
]


@router.get("/sources")
async def knowledge_sources(
    user=Depends(get_current_user),
):
    """The policy/knowledge sources available to the Evidence agent."""
    return _SOURCES
