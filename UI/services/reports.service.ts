import { mockReports } from "@/data/mock-reports";
import type { ReportArtifact } from "@/types/domain";

export async function getReports(): Promise<ReportArtifact[]> {
  return mockReports;
}
