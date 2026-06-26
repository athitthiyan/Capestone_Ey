"use client";

import { useQuery } from "@tanstack/react-query";
import { getAgentHealth, getAgentWorkflow } from "@/services/agents.service";

export function useAgentWorkflow() {
  return useQuery({
    queryKey: ["agent-workflow"],
    queryFn: getAgentWorkflow,
  });
}

export function useAgentHealth() {
  return useQuery({
    queryKey: ["agent-health"],
    queryFn: getAgentHealth,
  });
}
