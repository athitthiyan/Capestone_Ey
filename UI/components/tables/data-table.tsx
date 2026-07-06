"use client";

import {
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type PaginationState,
  type SortingState,
} from "@tanstack/react-table";
import { ArrowUpDown, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type DataTableProps<TData> = {
  columns: ColumnDef<TData>[];
  data: TData[];
  emptyLabel: string;
  initialPageSize?: number;
  pageSizeOptions?: number[];
};

const DEFAULT_PAGE_SIZE_OPTIONS = [25, 50, 100];

export function SortButton({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      {label}
      <ArrowUpDown className="h-3 w-3" aria-hidden="true" />
    </span>
  );
}

export function DataTable<TData>({
  columns,
  data,
  emptyLabel,
  initialPageSize = 25,
  pageSizeOptions = DEFAULT_PAGE_SIZE_OPTIONS,
}: DataTableProps<TData>) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: initialPageSize,
  });
  const table = useReactTable({
    data,
    columns,
    state: { pagination, sorting },
    onSortingChange: setSorting,
    onPaginationChange: setPagination,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });
  const totalRows = data.length;
  const visibleRows = table.getRowModel().rows;
  const firstVisibleRow = totalRows === 0 ? 0 : pagination.pageIndex * pagination.pageSize + 1;
  const lastVisibleRow = Math.min(totalRows, firstVisibleRow + visibleRows.length - 1);
  const pageCount = table.getPageCount();

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-card">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] border-collapse text-left text-sm">
          <thead className="bg-muted/70 text-xs uppercase tracking-[0.08em] text-muted-foreground">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th key={header.id} className="border-b border-border px-4 py-3 font-medium">
                    {header.isPlaceholder ? null : header.column.getCanSort() ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="-ml-3 h-7 text-xs uppercase tracking-[0.08em]"
                        onClick={header.column.getToggleSortingHandler()}
                      >
                        {flexRender(header.column.columnDef.header, header.getContext())}
                      </Button>
                    ) : (
                      flexRender(header.column.columnDef.header, header.getContext())
                    )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {visibleRows.length ? (
              visibleRows.map((row) => (
                <tr key={row.id} className="border-b border-border/70 last:border-b-0 hover:bg-muted/40">
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className={cn("px-4 py-3 align-middle text-muted-foreground")}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={columns.length} className="px-4 py-10 text-center text-muted-foreground">
                  {emptyLabel}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="flex flex-col gap-3 border-t border-border px-4 py-3 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
        <p>
          Showing {firstVisibleRow}-{lastVisibleRow} of {totalRows}
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2">
            <span>Rows</span>
            <select
              className="h-8 rounded-md border border-input bg-background px-2 text-xs text-foreground"
              value={pagination.pageSize}
              onChange={(event) => {
                table.setPageSize(Number(event.target.value));
              }}
            >
              {pageSizeOptions.map((pageSize) => (
                <option key={pageSize} value={pageSize}>
                  {pageSize}
                </option>
              ))}
            </select>
          </label>
          <span className="min-w-20 text-center">
            Page {pageCount === 0 ? 0 : pagination.pageIndex + 1} of {pageCount}
          </span>
          <div className="flex items-center gap-1">
            <Button
              aria-label="First page"
              disabled={!table.getCanPreviousPage()}
              size="icon"
              title="First page"
              type="button"
              variant="ghost"
              onClick={() => table.firstPage()}
            >
              <ChevronsLeft className="h-4 w-4" aria-hidden="true" />
            </Button>
            <Button
              aria-label="Previous page"
              disabled={!table.getCanPreviousPage()}
              size="icon"
              title="Previous page"
              type="button"
              variant="ghost"
              onClick={() => table.previousPage()}
            >
              <ChevronLeft className="h-4 w-4" aria-hidden="true" />
            </Button>
            <Button
              aria-label="Next page"
              disabled={!table.getCanNextPage()}
              size="icon"
              title="Next page"
              type="button"
              variant="ghost"
              onClick={() => table.nextPage()}
            >
              <ChevronRight className="h-4 w-4" aria-hidden="true" />
            </Button>
            <Button
              aria-label="Last page"
              disabled={!table.getCanNextPage()}
              size="icon"
              title="Last page"
              type="button"
              variant="ghost"
              onClick={() => table.lastPage()}
            >
              <ChevronsRight className="h-4 w-4" aria-hidden="true" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
