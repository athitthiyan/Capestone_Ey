import { dashboardSummary } from "@/data/mock-cases";
import { agentWorkflow } from "@/data/mock-agents";
import type { AgentHealth, PipelineStep } from "@/types/domain";

export async function getAgentHealth(): Promise<AgentHealth[]> {
  return dashboardSummary.agentHealth;
}

export async function getAgentWorkflow(): Promise<PipelineStep[]> {
  return agentWorkflow;
}
