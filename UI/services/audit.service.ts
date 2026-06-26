import { mockAuditEvents } from "@/data/mock-audit-logs";
import type { AuditEvent } from "@/types/domain";

export async function getAuditEvents(caseId?: string): Promise<AuditEvent[]> {
  if (!caseId) {
    return mockAuditEvents;
  }

  return mockAuditEvents.filter((event) => event.caseId === caseId);
}
