import { mockReviewHistory } from "@/data/mock-reviews";
import type { ReviewHistoryItem } from "@/types/domain";

export async function getReviewHistory(): Promise<ReviewHistoryItem[]> {
  return mockReviewHistory;
}
