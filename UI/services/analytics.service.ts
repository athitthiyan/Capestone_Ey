import { apiRequest } from "@/services/api";
import type { AgentAccuracy, AnalyticsKpi, AnalyticsPoint } from "@/types/domain";

type ApiTrendPoint = { week: string; confidence: number; verifier_rate: number };

export async function getAnalyticsTrend(): Promise<AnalyticsPoint[]> {
  const rows = await apiRequest<ApiTrendPoint[]>("/analytics/trend");
  return rows.map((row) => ({
    week: row.week,
    confidence: row.confidence,
    verifierRate: row.verifier_rate,
  }));
}

export async function getAgentAccuracy(): Promise<AgentAccuracy[]> {
  return apiRequest<AgentAccuracy[]>("/analytics/agent-accuracy");
}

export async function getAnalyticsKpis(): Promise<AnalyticsKpi[]> {
  return apiRequest<AnalyticsKpi[]>("/analytics/kpis");
}
