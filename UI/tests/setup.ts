import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    refresh: vi.fn(),
  }),
}));

process.env.NEXT_PUBLIC_API_BASE_URL = "http://localhost:8000/api/v1";
process.env.NEXT_PUBLIC_API_USERNAME = "";
process.env.NEXT_PUBLIC_API_PASSWORD = "";
process.env.NEXT_PUBLIC_API_TOKEN = "";

const investigation = {
  id: "case-fixture-1",
  transaction_id: "TXN-001",
  vendor: "Live Vendor Ltd",
  category: "consulting",
  amount: 75000,
  risk: "high",
  confidence: 0.82,
  flags: ["high risk", "human review"],
  status: "human_review",
  owner: "Audit team",
  reviewer: "Reviewer",
  posted_at: "2026-06-21T10:00:00Z",
  due_at: "2026-06-28T10:00:00Z",
  materiality: 50000,
  description: "Fixture investigation loaded through the API service layer.",
  created_at: "2026-06-21T10:00:00Z",
};

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

globalThis.fetch = async (input, init) => {
  const method = input instanceof Request ? input.method : init?.method ?? "GET";
  const rawUrl = input instanceof Request ? input.url : String(input);
  const url = new URL(rawUrl);
  const path = url.pathname.replace(/^\/api\/v1/, "");

  if (path === "/investigations/stats/summary") {
    return jsonResponse({
      total: 1,
      avg_confidence: 0.82,
      by_risk: { high: 1 },
      by_status: { human_review: 1 },
      auto_cleared: 0,
      in_review: 1,
      manual: 1,
    });
  }

  if (path === "/investigations" && method === "POST") {
    const body =
      input instanceof Request
        ? ((await input.json()) as Record<string, unknown>)
        : init?.body
          ? (JSON.parse(String(init.body)) as Record<string, unknown>)
          : {};

    return jsonResponse(
      {
        ...investigation,
        id: "case-created-1",
        transaction_id: body.transaction_id ?? "TXN-CREATED",
        vendor: body.vendor ?? "Created Vendor",
        category: body.category ?? "created",
        amount: body.amount ?? 1000,
        materiality: body.materiality ?? 25000,
        description: body.description ?? "Created from test.",
        owner: body.owner ?? "intake",
      },
      201,
    );
  }

  if (path === "/investigations/imported" && method === "DELETE") {
    return jsonResponse({
      deleted_count: 2,
      investigation_ids: ["case-imported-1", "case-imported-2"],
      message: "Deleted 2 imported intake investigation(s).",
    });
  }

  if (path === "/investigations") {
    return jsonResponse({ total: 1, skip: 0, limit: 500, investigations: [investigation] });
  }

  if (path === `/investigations/${investigation.id}`) {
    return jsonResponse(investigation);
  }

  if (path.match(/^\/investigations\/[^/]+\/execute$/) && method === "POST") {
    const caseId = path.split("/")[2];

    return jsonResponse({
      investigation_id: caseId,
      task_id: null,
      status: "running",
      message: "Investigation running in-process",
    });
  }

  if (path === `/investigations/${investigation.id}/debate`) {
    return jsonResponse([
      {
        id: "debate-1",
        round: 1,
        speaker: "Challenger",
        message: "Question the related-party rationale.",
        token_count: 120,
        created_at: "2026-06-21T11:00:00Z",
      },
      {
        id: "debate-2",
        round: 2,
        speaker: "adjudicator",
        message: "Verdict: high risk at 82% confidence.",
        token_count: 90,
        confidence: 0.82,
        created_at: "2026-06-21T11:05:00Z",
      },
    ]);
  }

  if (path === `/investigations/${investigation.id}/evidence`) {
    return jsonResponse([
      {
        id: "evidence-1",
        source: "Ledger",
        content: "Payment exceeds materiality.",
        citations: ["ledger/TXN-001"],
        relevance_score: 0.9,
        created_at: "2026-06-21T11:00:00Z",
      },
    ]);
  }

  if (path === `/investigations/${investigation.id}/verification`) {
    return jsonResponse([
      {
        id: "verification-1",
        claim_text: "Payment exceeds materiality.",
        is_grounded: true,
        explanation: "Ledger evidence supports the claim.",
        supporting_evidence: ["evidence-1"],
        created_at: "2026-06-21T11:10:00Z",
      },
    ]);
  }

  if (path === `/claims/${investigation.id}/verification`) {
    return jsonResponse({
      id: "evidence-verification-1",
      claim_id: investigation.id,
      category: "generic",
      claimed_amount: 75000,
      fetched_amount: null,
      min_acceptable_amount: null,
      max_acceptable_amount: null,
      difference_amount: null,
      difference_percentage: null,
      tolerance_percentage: 0.3,
      provider_name: "generic_third_party_provider",
      provider_reference_id: null,
      verification_status: "API_UNAVAILABLE",
      confidence_score: 0,
      reason: "No real-time third-party provider URL is configured for category 'generic'.",
      created_at: "2026-06-21T10:01:00Z",
      updated_at: "2026-06-21T10:01:00Z",
    });
  }

  if (path.match(/^\/claims\/[^/]+\/verify-evidence$/) && method === "POST") {
    const caseId = path.split("/")[2];

    return jsonResponse(
      {
        id: "evidence-verification-rerun-1",
        claim_id: caseId,
        category: "flight",
        claimed_amount: 20000,
        fetched_amount: 7500,
        min_acceptable_amount: 5625,
        max_acceptable_amount: 9375,
        difference_amount: 12500,
        difference_percentage: 1.666667,
        tolerance_percentage: 0.25,
        provider_name: "live_flight_fare_api",
        provider_reference_id: "LIVE-FLIGHT-123",
        verification_status: "FLAGGED",
        confidence_score: 0.78,
        reason: "Claimed amount is outside the accepted +/-25% range.",
        created_at: "2026-06-21T10:02:00Z",
        updated_at: "2026-06-21T10:02:00Z",
      },
      201,
    );
  }

  if (path === `/investigations/${investigation.id}/audit`) {
    return jsonResponse([
      {
        id: "audit-1",
        type: "case_created",
        data: {
          event_type: "case_created",
          investigation_id: investigation.id,
          actor: "system",
          details: {},
          timestamp: "2026-06-21T10:00:00Z",
        },
        hash: "abcdef1234567890",
        sequence: 1,
      },
    ]);
  }

  if (path === `/investigations/${investigation.id}/replay`) {
    return jsonResponse([]);
  }

  if (path === "/evaluation/summary") {
    return jsonResponse({ cases: 0, metrics: [], conclusion: "" });
  }

  if (path === "/analytics/trend" || path === "/analytics/agent-accuracy" || path === "/analytics/kpis") {
    return jsonResponse([]);
  }

  if (path === "/reports") {
    return jsonResponse([]);
  }

  if (path === "/knowledge/sources") {
    return jsonResponse([]);
  }

  if (path === "/audit/recent") {
    return jsonResponse([]);
  }

  if (path === "/reviews/queue") {
    return jsonResponse([
      {
        id: "queue-1",
        investigation_id: investigation.id,
        title: "Live Vendor Ltd / consulting",
        risk: "high",
        confidence: 0.82,
        due_at: "2026-06-28T10:00:00Z",
        queue: "reviewer",
        assigned_to: "reviewer_pool",
        priority: 2,
        status: "pending",
        notes: "Confidence gate routed case to review.",
      },
    ]);
  }

  return jsonResponse({ detail: "Unhandled test endpoint" }, 404);
};
