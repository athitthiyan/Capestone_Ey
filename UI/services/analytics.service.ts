import { agentAccuracy, analyticsKpis, analyticsTrend } from "@/data/mock-analytics";
import type { AgentAccuracy, AnalyticsKpi, AnalyticsPoint } from "@/types/domain";

export async function getAnalyticsTrend(): Promise<AnalyticsPoint[]> {
  return analyticsTrend;
}

export async function getAgentAccuracy(): Promise<AgentAccuracy[]> {
  return agentAccuracy;
}

export async function getAnalyticsKpis(): Promise<AnalyticsKpi[]> {
  return [...analyticsKpis];
}
