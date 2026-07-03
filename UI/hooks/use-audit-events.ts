"use client";

import { useQuery } from "@tanstack/react-query";
import { getAuditEvents } from "@/services/audit.service";

export function useAuditEvents(
  caseId?: string,
  options: { enabled?: boolean; limit?: number } = {},
) {
  return useQuery({
    queryKey: ["audit-events", caseId ?? "all", options.limit ?? 200],
    queryFn: () => getAuditEvents(caseId, { limit: options.limit }),
    enabled: options.enabled ?? true,
  });
}
