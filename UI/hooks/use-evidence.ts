"use client";

import { useQuery } from "@tanstack/react-query";
import { getEvidence } from "@/services/evidence.service";

export function useEvidence(caseId?: string) {
  return useQuery({
    queryKey: ["evidence", caseId ?? "all"],
    queryFn: () => getEvidence(caseId),
  });
}
