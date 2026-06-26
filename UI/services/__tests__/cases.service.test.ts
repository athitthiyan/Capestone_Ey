import { describe, expect, it } from "vitest";
import { getDashboardSummary, getInvestigation, getInvestigations, getReviewQueue } from "@/services/cases.service";

describe("cases service", () => {
  it("returns dashboard summary with recent investigations", async () => {
    const summary = await getDashboardSummary();

    expect(summary.engagement).toBe("ACME Holdings");
    expect(summary.recentInvestigations.length).toBeGreaterThan(0);
    expect(summary.metrics.some((metric) => metric.label === "Average confidence")).toBe(true);
  });

  it("looks up a case by id", async () => {
    const investigation = await getInvestigation("CASE-0007");

    expect(investigation?.vendor).toBe("Mehta Family Holdings");
    expect(investigation?.risk).toBe("critical");
  });

  it("keeps review queue scoped to cases needing human judgement", async () => {
    const investigations = await getInvestigations();
    const queue = await getReviewQueue();
    const queueCaseIds = new Set(queue.map((item) => item.caseId));

    expect(queue.length).toBeGreaterThan(0);
    expect(investigations.some((item) => queueCaseIds.has(item.id))).toBe(true);
    expect(queue.every((item) => item.confidence < 1)).toBe(true);
  });
});
