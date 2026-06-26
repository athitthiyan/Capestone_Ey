import { mockEvidence } from "@/data/mock-evidence";
import type { EvidenceSource } from "@/types/domain";

export async function getEvidence(caseId?: string): Promise<EvidenceSource[]> {
  if (!caseId) {
    return mockEvidence;
  }

  return mockEvidence.filter((source) => source.linkedCases.includes(caseId));
}
