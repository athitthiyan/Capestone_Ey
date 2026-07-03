"use client";

import { useQuery } from "@tanstack/react-query";
import { getInvestigationWorkspace } from "@/services/workspace.service";

export function useCaseWorkspace(caseId?: string) {
  return useQuery({
    queryKey: ["case-workspace", caseId ?? ""],
    queryFn: () => getInvestigationWorkspace(caseId as string),
    enabled: Boolean(caseId),
    staleTime: 15_000,
  });
}
