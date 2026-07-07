"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { Pencil, Archive } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DataTable, SortButton } from "@/components/tables/data-table";
import { statusLabel } from "@/lib/status";
import type {
  EmployeeTransaction,
  EmployeeTransactionStatus,
} from "@/types/domain";

type BadgeTone = "default" | "primary" | "success" | "warning" | "danger" | "info";

const statusTone: Record<EmployeeTransactionStatus, BadgeTone> = {
  pending: "warning",
  completed: "success",
  failed: "danger",
  cancelled: "default",
  archived: "default",
};

export function formatAmount(amount: number, currency: string) {
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      maximumFractionDigits: 2,
    }).format(amount);
  } catch {
    return `${currency} ${amount.toFixed(2)}`;
  }
}

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString();
}

type Props = {
  transactions: EmployeeTransaction[];
  onEdit: (transaction: EmployeeTransaction) => void;
  onArchive: (transaction: EmployeeTransaction) => void;
  archivingId?: string | null;
};

export function EmployeeTransactionsTable({ transactions, onEdit, onArchive, archivingId }: Props) {
  const columns: ColumnDef<EmployeeTransaction>[] = [
    {
      accessorKey: "referenceId",
      header: "Reference",
      cell: ({ row }) => (
        <div>
          <p className="font-mono text-foreground">{row.original.referenceId ?? "—"}</p>
          <p className="max-w-[220px] truncate text-xs text-muted-foreground">
            {row.original.description ?? ""}
          </p>
        </div>
      ),
    },
    {
      accessorKey: "employeeId",
      header: "Employee",
      cell: ({ row }) => <span className="font-mono text-xs text-foreground">{row.original.employeeId}</span>,
    },
    {
      accessorKey: "transactionType",
      header: "Type",
      cell: ({ row }) => <Badge variant="primary">{statusLabel(row.original.transactionType)}</Badge>,
    },
    {
      accessorKey: "amount",
      header: () => <SortButton label="Amount" />,
      cell: ({ row }) => (
        <span className="font-mono text-foreground">{formatAmount(row.original.amount, row.original.currency)}</span>
      ),
    },
    {
      accessorKey: "status",
      header: "Status",
      cell: ({ row }) => <Badge variant={statusTone[row.original.status]}>{statusLabel(row.original.status)}</Badge>,
    },
    {
      accessorKey: "transactionDate",
      header: () => <SortButton label="Date" />,
      cell: ({ row }) => <span className="text-foreground">{formatDate(row.original.transactionDate)}</span>,
    },
    {
      id: "actions",
      header: "",
      cell: ({ row }) => (
        <div className="flex justify-end gap-1">
          <Button variant="ghost" size="sm" onClick={() => onEdit(row.original)}>
            <Pencil className="h-4 w-4" aria-hidden="true" />
            Edit
          </Button>
          {row.original.isArchived ? null : (
            <Button
              variant="ghost"
              size="sm"
              disabled={archivingId === row.original.id}
              onClick={() => onArchive(row.original)}
            >
              <Archive className="h-4 w-4" aria-hidden="true" />
              Archive
            </Button>
          )}
        </div>
      ),
    },
  ];

  return <DataTable columns={columns} data={transactions} emptyLabel="No transactions match your filters." />;
}
