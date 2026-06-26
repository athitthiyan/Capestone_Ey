import type { ReportArtifact } from "@/types/domain";

export const mockReports: ReportArtifact[] = [
  {
    id: "RPT-0007",
    title: "CASE-0007 Professional skepticism memo",
    status: "draft",
    updatedAt: "2026-06-24 11:12 IST",
    confidence: 0.86,
    audience: "Engagement team",
    sections: ["Executive conclusion", "Evidence map", "Agent debate", "Open reviewer decisions"],
    riskVerdict: "critical",
    executiveSummary:
      "Critical related-party and cutoff indicators remain unresolved. Human review should hold reliance until disclosure and SOW evidence are complete.",
    humanDecision: "Awaiting partner signature",
    reviewerSignature: "pending",
  },
  {
    id: "RPT-Q2",
    title: "FY26 Q2 high-risk exceptions pack",
    status: "ready",
    updatedAt: "2026-06-24 09:45 IST",
    confidence: 0.91,
    audience: "Partner",
    sections: ["Risk summary", "Material cases", "Verifier exceptions", "Management follow-up"],
    riskVerdict: "high",
    executiveSummary:
      "Quarter-close exceptions are concentrated in new vendors and manual approval overrides, with verifier exceptions isolated to three cases.",
    humanDecision: "Partner review in progress",
    reviewerSignature: "p.nair / staged",
  },
  {
    id: "RPT-AC",
    title: "Audit committee AI assurance appendix",
    status: "approved",
    updatedAt: "2026-06-22 16:20 IST",
    confidence: 0.94,
    audience: "Audit committee",
    sections: ["Model governance", "Human oversight", "Immutable audit log", "Exceptions"],
    riskVerdict: "medium",
    executiveSummary:
      "AI-assisted workflow operated within materiality and oversight policy, with immutable evidence for all escalated decisions.",
    humanDecision: "Approved for committee appendix",
    reviewerSignature: "a.sharma / 2026-06-22",
  },
];
