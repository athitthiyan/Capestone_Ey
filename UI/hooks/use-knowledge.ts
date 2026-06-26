"use client";

import { useQuery } from "@tanstack/react-query";
import { getKnowledgeSources } from "@/services/knowledge.service";

export function useKnowledgeSources() {
  return useQuery({
    queryKey: ["knowledge-sources"],
    queryFn: getKnowledgeSources,
  });
}
