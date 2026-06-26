"use client";

import { useQuery } from "@tanstack/react-query";
import { getReviewHistory } from "@/services/reviews.service";

export function useReviewHistory(caseId: string) {
  return useQuery({
    queryKey: ["review-history", caseId],
    queryFn: getReviewHistory,
  });
}
