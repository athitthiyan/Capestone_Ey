"use client";

import { useQuery } from "@tanstack/react-query";
import { getReports } from "@/services/reports.service";

export function useReports(options: { caseId?: string } = {}) {
  return useQuery({
    queryKey: ["reports", options.caseId ?? ""],
    queryFn: () => getReports(options),
  });
}
