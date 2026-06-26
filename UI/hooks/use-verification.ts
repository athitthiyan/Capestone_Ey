"use client";

import { useQuery } from "@tanstack/react-query";
import { getVerificationClaims } from "@/services/verification.service";

export function useVerificationClaims(caseId: string) {
  return useQuery({
    queryKey: ["verification", caseId],
    queryFn: getVerificationClaims,
  });
}
