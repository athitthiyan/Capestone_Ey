import type { ReviewHistoryItem } from "@/types/domain";

export const mockReviewHistory: ReviewHistoryItem[] = [
  {
    id: "REV-1",
    actor: "Confidence gate",
    action: "escalated",
    comment: "Critical risk and amount above materiality require partner review.",
    timestamp: "2026-06-24 11:03 IST",
    signature: "system/hash:ef394019",
  },
  {
    id: "REV-2",
    actor: "Priya Nair",
    action: "requested_evidence",
    comment: "Request signed SOW and external registry extract before final conclusion.",
    timestamp: "2026-06-24 11:18 IST",
    signature: "p.nair",
  },
  {
    id: "REV-3",
    actor: "Investigation state",
    action: "resumed",
    comment: "Evidence request routed back to Evidence agent with durable resume token.",
    timestamp: "2026-06-24 11:21 IST",
    signature: "resume/CASE-0007",
  },
];
