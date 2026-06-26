"use client";

import { useQuery } from "@tanstack/react-query";
import { getAgentAccuracy, getAnalyticsKpis, getAnalyticsTrend } from "@/services/analytics.service";

export function useAnalyticsTrend() {
  return useQuery({
    queryKey: ["analytics-trend"],
    queryFn: getAnalyticsTrend,
  });
}

export function useAgentAccuracy() {
  return useQuery({
    queryKey: ["agent-accuracy"],
    queryFn: getAgentAccuracy,
  });
}

export function useAnalyticsKpis() {
  return useQuery({
    queryKey: ["analytics-kpis"],
    queryFn: getAnalyticsKpis,
  });
}
