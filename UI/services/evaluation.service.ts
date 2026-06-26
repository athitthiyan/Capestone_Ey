import { mockEvaluationSummary } from "@/data/mock-evaluation";
import type { EvaluationSummary } from "@/types/domain";

export async function getEvaluationSummary(): Promise<EvaluationSummary> {
  return mockEvaluationSummary;
}
