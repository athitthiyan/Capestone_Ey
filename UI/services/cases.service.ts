import { dashboardSummary, mockInvestigations } from "@/data/mock-cases";
import type { DashboardSummary, Investigation, ReviewQueueItem } from "@/types/domain";

export async function getDashboardSummary(): Promise<DashboardSummary> {
  return dashboardSummary;
}

export async function getInvestigations(): Promise<Investigation[]> {
  return mockInvestigations;
}

export async function getInvestigation(caseId: string): Promise<Investigation | undefined> {
  return mockInvestigations.find((investigation) => investigation.id === caseId);
}

export async function getReviewQueue(): Promise<ReviewQueueItem[]> {
  return mockInvestigations
    .filter((investigation) => investigation.status === "human_review" || investigation.risk === "critical")
    .map((investigation) => ({
      id: `QUEUE-${investigation.id}`,
      caseId: investigation.id,
      title: `${investigation.vendor} / ${investigation.category}`,
      risk: investigation.risk,
      confidence: investigation.confidence,
      dueAt: investigation.dueAt,
      queue: investigation.risk === "critical" ? "partner" : "reviewer",
    }));
}
