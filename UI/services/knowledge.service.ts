import { apiRequest } from "@/services/api";
import type { KnowledgeSource } from "@/types/domain";

type ApiKnowledgeSource = {
  id: string;
  title: string;
  description: string;
  owner: string;
  count: string;
  freshness: string;
  status: KnowledgeSource["status"];
  clause_preview: string;
  version_history: string[];
  citation_ids: string[];
  embedding_status: KnowledgeSource["embeddingStatus"];
};

export async function getKnowledgeSources(): Promise<KnowledgeSource[]> {
  const rows = await apiRequest<ApiKnowledgeSource[]>("/knowledge/sources");

  return rows.map((row) => ({
    id: row.id,
    title: row.title,
    description: row.description,
    owner: row.owner,
    count: row.count,
    freshness: row.freshness,
    status: row.status,
    clausePreview: row.clause_preview,
    versionHistory: row.version_history,
    citationIds: row.citation_ids,
    embeddingStatus: row.embedding_status,
  }));
}
