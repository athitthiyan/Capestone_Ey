import { describe, expect, it } from "vitest";
import { getEvaluationSummary } from "@/services/evaluation.service";

describe("evaluation service", () => {
  it("returns an A/B evaluation summary", async () => {
    const summary = await getEvaluationSummary();

    expect(summary.cases).toBeGreaterThan(0);
    expect(summary.kpis.length).toBeGreaterThan(0);
  });

  it("includes a single-prompt vs crew comparison", async () => {
    const summary = await getEvaluationSummary();

    expect(summary.comparison.length).toBeGreaterThan(0);
    expect(summary.comparison.some((row) => row.better)).toBe(true);
  });

  it("keeps the seeded hallucination test within bounds", async () => {
    const summary = await getEvaluationSummary();

    expect(summary.hallucination.every((result) => result.count <= result.total)).toBe(true);
  });
});
