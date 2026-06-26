import type { DebateArgument } from "@/types/domain";

export const mockDebateArguments: DebateArgument[] = [
  {
    id: "ARG-C-1",
    side: "challenger",
    title: "Related-party signal is not resolved",
    timestamp: "2026-06-24 10:31 IST",
    summary:
      "Vendor ownership overlaps with a declared family relationship and the case lacks a documented disclosure assessment.",
    tags: ["RPT", "Disclosure", "Management bias"],
    footer: "Requires independent corroboration from legal entity registry.",
    scoreLabel: "Objection strength 0.84",
    citations: ["MDM/Vendors/MEHTA-FAMILY-HOLDINGS", "Policy/RPT/Section-4.2"],
    confidence: 0.84,
    details:
      "The challenger gives weight to relationship evidence, materiality breach, and missing disclosure assessment. The position remains high severity until registry evidence is attached.",
  },
  {
    id: "ARG-D-1",
    side: "defender",
    title: "Business purpose has partial support",
    timestamp: "2026-06-24 10:33 IST",
    summary:
      "The cost center owner approved the service category and the invoice aligns with the transformation budget.",
    tags: ["Approval", "Budget", "Completeness"],
    footer: "Evidence is useful but not enough to close the RPT assertion.",
    scoreLabel: "Defense strength 0.73",
    citations: ["ERP/AP/2026/Q2/INV-7784"],
    confidence: 0.73,
    details:
      "The defender explains a benign consulting-retainer scenario but conditions it on signed contract, deliverables, and independent approval evidence.",
  },
  {
    id: "ARG-C-2",
    side: "challenger",
    title: "Cutoff and deliverable timing remain suspicious",
    timestamp: "2026-06-24 10:36 IST",
    summary:
      "The SOW was dated after service start and the invoice was posted two days before quarter close.",
    tags: ["Cutoff", "Occurrence", "SOW"],
    footer: "Verifier should inspect source dates and immutable log events.",
    scoreLabel: "Objection strength 0.79",
    citations: ["ERP/AP/2026/Q2/INV-7784", "Analytics/AP/VendorTrend/MEHTA"],
    confidence: 0.79,
    details:
      "The challenger flags cutoff risk because service documentation is dated after service start and close-period posting increases management-bias risk.",
  },
  {
    id: "ARG-A-1",
    side: "adjudicator",
    title: "High-risk verdict with evidence request",
    timestamp: "2026-06-24 10:41 IST",
    summary:
      "Adjudicator keeps the case high risk, accepts partial business-purpose support, and routes missing registry and SOW evidence to human review.",
    tags: ["Verdict", "Confidence gate", "Escalation"],
    footer: "Disposition: hold reliance until reviewer signs decision or evidence is revised.",
    scoreLabel: "Verdict confidence 0.86",
    citations: ["Policy/RPT/Section-4.2", "MDM/Vendors/MEHTA-FAMILY-HOLDINGS"],
    confidence: 0.86,
    details:
      "The adjudicator weighs both views and identifies the minimum evidence required to move from partner review to report-ready status.",
  },
];
