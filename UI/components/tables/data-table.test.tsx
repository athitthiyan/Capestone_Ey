import { fireEvent, render, screen } from "@testing-library/react";
import type { ColumnDef } from "@tanstack/react-table";
import { describe, expect, it } from "vitest";
import { DataTable } from "@/components/tables/data-table";

type TestRow = {
  id: string;
  name: string;
};

const columns: ColumnDef<TestRow>[] = [
  {
    accessorKey: "id",
    header: "ID",
  },
  {
    accessorKey: "name",
    header: "Name",
  },
];

const rows = Array.from({ length: 30 }, (_, index) => ({
  id: `row-${String(index + 1).padStart(2, "0")}`,
  name: `Row ${index + 1}`,
}));

describe("DataTable", () => {
  it("paginates rows instead of rendering the full data set", () => {
    render(<DataTable columns={columns} data={rows} emptyLabel="No rows" />);

    expect(screen.getByText("Row 1")).toBeInTheDocument();
    expect(screen.queryByText("Row 26")).not.toBeInTheDocument();
    expect(screen.getByText("Showing 1-25 of 30")).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Next page"));

    expect(screen.queryByText("Row 1")).not.toBeInTheDocument();
    expect(screen.getByText("Row 26")).toBeInTheDocument();
    expect(screen.getByText("Showing 26-30 of 30")).toBeInTheDocument();
  });
});
