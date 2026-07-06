import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FlaggedRowsTable } from "@/components/intake/flagged-rows-table";
import type { FlaggedRow } from "@/types/domain";

const rows: FlaggedRow[] = Array.from({ length: 30 }, (_, index) => ({
  txnId: `TXN-${String(index + 1).padStart(3, "0")}`,
  vendor: `Vendor ${index + 1}`,
  account: "Travel",
  amount: "$1,000.00",
  rules: ["high_amount"],
}));

describe("FlaggedRowsTable", () => {
  it("keeps large flagged-row previews paginated", () => {
    render(<FlaggedRowsTable rows={rows} />);

    expect(screen.getByText("TXN-001")).toBeInTheDocument();
    expect(screen.queryByText("TXN-026")).not.toBeInTheDocument();
    expect(screen.getByText("Showing 1-25 of 30")).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Next flagged rows page"));

    expect(screen.queryByText("TXN-001")).not.toBeInTheDocument();
    expect(screen.getByText("TXN-026")).toBeInTheDocument();
    expect(screen.getByText("Showing 26-30 of 30")).toBeInTheDocument();
  });
});
