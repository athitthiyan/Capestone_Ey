"use client";

import { ArrowRight, ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { routes } from "@/constants/routes";
import type { FlaggedRow } from "@/types/domain";

const FLAGGED_ROWS_PAGE_SIZE = 25;

export function FlaggedRowsTable({ rows }: { rows: FlaggedRow[] }) {
  const [pageIndex, setPageIndex] = useState(0);
  const totalPages = Math.max(1, Math.ceil(rows.length / FLAGGED_ROWS_PAGE_SIZE));
  const firstVisibleRow = rows.length === 0 ? 0 : pageIndex * FLAGGED_ROWS_PAGE_SIZE + 1;
  const visibleRows = useMemo(
    () => rows.slice(pageIndex * FLAGGED_ROWS_PAGE_SIZE, (pageIndex + 1) * FLAGGED_ROWS_PAGE_SIZE),
    [pageIndex, rows],
  );
  const lastVisibleRow = Math.min(rows.length, firstVisibleRow + visibleRows.length - 1);

  useEffect(() => {
    setPageIndex((current) => Math.min(current, totalPages - 1));
  }, [totalPages]);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Flagged rows &rarr; cases</CardTitle>
        <Link
          href={routes.investigations}
          className="inline-flex items-center gap-1 text-xs font-medium text-primary"
        >
          Open queue <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </Link>
      </CardHeader>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs uppercase tracking-[0.12em] text-muted-foreground">
                <th scope="col" className="px-4 py-2 font-medium">
                  Txn
                </th>
                <th scope="col" className="px-4 py-2 font-medium">
                  Vendor / account
                </th>
                <th scope="col" className="px-4 py-2 font-medium">
                  Amount
                </th>
                <th scope="col" className="px-4 py-2 font-medium">
                  Rules fired
                </th>
              </tr>
            </thead>
            <tbody>
              {visibleRows.map((row) => (
                <tr key={row.txnId} className="border-b border-border last:border-0">
                  <td className="px-4 py-3 font-mono text-muted-foreground">{row.txnId}</td>
                  <td className="px-4 py-3">
                    <span className="text-foreground">{row.vendor}</span>{" "}
                    <span className="text-muted-foreground">&middot; {row.account}</span>
                  </td>
                  <td className="px-4 py-3 font-mono">{row.amount}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {row.rules.map((rule) => (
                        <Badge key={rule} variant="default">
                          {rule}
                        </Badge>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex flex-col gap-3 border-t border-border px-4 py-3 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
          <p>
            Showing {firstVisibleRow}-{lastVisibleRow} of {rows.length}
          </p>
          <div className="flex items-center gap-2">
            <span>
              Page {pageIndex + 1} of {totalPages}
            </span>
            <Button
              aria-label="Previous flagged rows page"
              disabled={pageIndex === 0}
              size="icon"
              title="Previous page"
              type="button"
              variant="ghost"
              onClick={() => setPageIndex((current) => Math.max(0, current - 1))}
            >
              <ChevronLeft className="h-4 w-4" aria-hidden="true" />
            </Button>
            <Button
              aria-label="Next flagged rows page"
              disabled={pageIndex >= totalPages - 1}
              size="icon"
              title="Next page"
              type="button"
              variant="ghost"
              onClick={() => setPageIndex((current) => Math.min(totalPages - 1, current + 1))}
            >
              <ChevronRight className="h-4 w-4" aria-hidden="true" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
