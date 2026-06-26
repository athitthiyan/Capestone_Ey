import { describe, expect, it } from "vitest";
import { getIntakeSummary, parseLedgerFile } from "@/services/intake.service";

describe("intake service", () => {
  it("returns a GL intake summary", async () => {
    const summary = await getIntakeSummary();

    expect(summary.fileName).toBe("sample_gl_1000.csv");
    expect(summary.rowsIngested).toBe(1000);
  });

  it("keeps flagged + cleared consistent with rows ingested", async () => {
    const summary = await getIntakeSummary();

    expect(summary.flagged + summary.cleared).toBe(summary.rowsIngested);
    expect(summary.flagged).toBeGreaterThan(0);
  });

  it("exposes deterministic rule statistics and flagged rows", async () => {
    const summary = await getIntakeSummary();

    expect(summary.ruleStats.length).toBeGreaterThan(0);
    expect(summary.ruleStats.every((rule) => rule.count >= 0)).toBe(true);
    expect(summary.flaggedRows.every((row) => row.rules.length > 0)).toBe(true);
  });

  it("parses uploaded CSV files and creates flagged rows", async () => {
    const file = new File(
      [
        [
          "txn_id,date,account,vendor,currency,amount_usd,fx_rate_used,posted_by",
          "TXN-1,2026-06-21T22:10:00Z,Consulting,Unknown Vendor,USD,30000,1.0,admin",
          "TXN-2,2026-06-22T10:00:00Z,Office,Staples,USD,312,1.0,ap.user",
        ].join("\n"),
      ],
      "ledger.csv",
      { type: "text/csv" },
    );

    const summary = await parseLedgerFile(file);

    expect(summary.fileName).toBe("ledger.csv");
    expect(summary.rowsIngested).toBe(2);
    expect(summary.flagged).toBe(1);
    expect(summary.flaggedRows[0].rules).toContain("materiality");
    expect(summary.flaggedRows[0].rules).toContain("unknown vendor");
  });
});
