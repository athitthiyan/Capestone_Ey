"use client";

import { useQuery } from "@tanstack/react-query";
import { getInvestigation } from "@/services/cases.service";

export function useInvestigation(caseId: string) {
  return useQuery({
    queryKey: ["investigation", caseId],
    queryFn: () => getInvestigation(caseId),
  });
}
