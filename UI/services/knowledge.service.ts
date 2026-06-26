import { mockKnowledgeSources } from "@/data/mock-knowledge";
import type { KnowledgeSource } from "@/types/domain";

export async function getKnowledgeSources(): Promise<KnowledgeSource[]> {
  return mockKnowledgeSources;
}
