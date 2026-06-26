"use client";

import { useQuery } from "@tanstack/react-query";
import { getDashboardSummary, getInvestigations, getReviewQueue } from "@/services/cases.service";

export function useDashboardSummary() {
  return useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: getDashboardSummary,
  });
}

export function useInvestigations() {
  return useQuery({
    queryKey: ["investigations"],
    queryFn: getInvestigations,
  });
}

export function useReviewQueue() {
  return useQuery({
    queryKey: ["review-queue"],
    queryFn: getReviewQueue,
  });
}
