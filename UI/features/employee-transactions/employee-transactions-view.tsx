"use client";

import { CheckCircle2, Filter, Plus, Wallet } from "lucide-react";
import { useMemo, useState } from "react";
import { EmployeeTransactionDialog } from "@/components/employee-transactions/employee-transaction-dialog";
import { EmployeeTransactionsTable, formatAmount } from "@/components/employee-transactions/employee-transactions-table";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  useArchiveEmployeeTransaction,
  useEmployeeTransactions,
  useEmployeeTransactionsByEmployee,
} from "@/hooks/use-employee-transactions";
import type { EmployeeTransactionFilters } from "@/services/employee-transactions.service";
import type {
  EmployeeTransaction,
  EmployeeTransactionStatus,
  EmployeeTransactionType,
} from "@/types/domain";

const pageSize = 20;

export function EmployeeTransactionsView() {
  const [employeeId, setEmployeeId] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<EmployeeTransactionStatus | "all">("all");
  const [typeFilter, setTypeFilter] = useState<EmployeeTransactionType | "all">("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [includeArchived, setIncludeArchived] = useState(false);
  const [page, setPage] = useState(1);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<EmployeeTransaction | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const filters: EmployeeTransactionFilters = useMemo(
    () => ({
      search: search.trim() || undefined,
      status: statusFilter === "all" ? undefined : statusFilter,
      type: typeFilter === "all" ? undefined : typeFilter,
      dateFrom: dateFrom || undefined,
      dateTo: dateTo || undefined,
      includeArchived,
      skip: (page - 1) * pageSize,
      limit: pageSize,
    }),
    [search, statusFilter, typeFilter, dateFrom, dateTo, includeArchived, page],
  );

  const scoped = Boolean(employeeId.trim());
  const allQuery = useEmployeeTransactions(filters, !scoped);
  const employeeQuery = useEmployeeTransactionsByEmployee(scoped ? employeeId.trim() : undefined, filters);
  const query = scoped ? employeeQuery : allQuery;

  const archiveMutation = useArchiveEmployeeTransaction();

  function resetFilters() {
    setEmployeeId("");
    setSearch("");
    setStatusFilter("all");
    setTypeFilter("all");
    setDateFrom("");
    setDateTo("");
    setIncludeArchived(false);
    setPage(1);
  }

  function openCreate() {
    setEditing(null);
    setDialogOpen(true);
  }

  function openEdit(transaction: EmployeeTransaction) {
    setEditing(transaction);
    setDialogOpen(true);
  }

  async function handleArchive(transaction: EmployeeTransaction) {
    try {
      await archiveMutation.mutateAsync(transaction.id);
      setSuccessMessage("Transaction archived.");
    } catch {
      setSuccessMessage(null);
    }
  }

  const transactions = query.data?.transactions ?? [];
  const total = query.data?.total ?? 0;
  const pageCount = Math.max(Math.ceil(total / pageSize), 1);
  const totalAmount = transactions.reduce((sum, item) => sum + item.amount, 0);
  const displayCurrency = transactions[0]?.currency ?? "USD";

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Wallet}
        eyebrow="Finance"
        title="Employee transactions"
        description="Store, review, and manage financial transactions linked to a specific employee. Filter by employee, status, type, or date range."
        actions={
          <>
            <Button variant="secondary" onClick={resetFilters}>
              <Filter className="h-4 w-4" aria-hidden="true" />
              Clear filters
            </Button>
            <Button onClick={openCreate}>
              <Plus className="h-4 w-4" aria-hidden="true" />
              New transaction
            </Button>
          </>
        }
      />

      {successMessage ? (
        <div className="flex items-center gap-2 rounded-md border border-success-border bg-success-soft px-4 py-2 text-sm text-success-foreground">
          <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
          {successMessage}
        </div>
      ) : null}

      <section className="grid gap-4 md:grid-cols-3" aria-label="Transaction summary">
        <Card>
          <CardContent className="p-4">
            <p className="text-xs uppercase tracking-[0.12em] text-muted-foreground">Matching transactions</p>
            <p className="mt-2 font-mono text-2xl text-foreground">{total}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-xs uppercase tracking-[0.12em] text-muted-foreground">On this page</p>
            <p className="mt-2 font-mono text-2xl text-foreground">{transactions.length}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-xs uppercase tracking-[0.12em] text-muted-foreground">Page total</p>
            <p className="mt-2 font-mono text-2xl text-foreground">{formatAmount(totalAmount, displayCurrency)}</p>
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-3 rounded-lg border border-border bg-card p-4 md:grid-cols-4" aria-label="Filters">
        <label className="text-xs text-muted-foreground md:col-span-2">
          Employee ID
          <Input
            className="mt-1"
            placeholder="Filter by a specific employee (users.id)"
            value={employeeId}
            onChange={(event) => {
              setEmployeeId(event.target.value);
              setPage(1);
            }}
          />
        </label>
        <label className="text-xs text-muted-foreground md:col-span-2">
          Search
          <Input
            className="mt-1"
            placeholder="Description or reference ID"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
          />
        </label>
        <label className="text-xs text-muted-foreground">
          Status
          <select
            className="mt-1 h-9 w-full rounded-md border border-input bg-background px-3 text-sm text-foreground"
            value={statusFilter}
            onChange={(event) => {
              setStatusFilter(event.target.value as EmployeeTransactionStatus | "all");
              setPage(1);
            }}
          >
            <option value="all">All statuses</option>
            <option value="pending">Pending</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="cancelled">Cancelled</option>
            <option value="archived">Archived</option>
          </select>
        </label>
        <label className="text-xs text-muted-foreground">
          Type
          <select
            className="mt-1 h-9 w-full rounded-md border border-input bg-background px-3 text-sm text-foreground"
            value={typeFilter}
            onChange={(event) => {
              setTypeFilter(event.target.value as EmployeeTransactionType | "all");
              setPage(1);
            }}
          >
            <option value="all">All types</option>
            <option value="credit">Credit</option>
            <option value="debit">Debit</option>
            <option value="reimbursement">Reimbursement</option>
            <option value="payroll">Payroll</option>
            <option value="bonus">Bonus</option>
            <option value="deduction">Deduction</option>
            <option value="adjustment">Adjustment</option>
          </select>
        </label>
        <label className="text-xs text-muted-foreground">
          From
          <Input
            className="mt-1"
            type="date"
            value={dateFrom}
            onChange={(event) => {
              setDateFrom(event.target.value);
              setPage(1);
            }}
          />
        </label>
        <label className="text-xs text-muted-foreground">
          To
          <Input
            className="mt-1"
            type="date"
            value={dateTo}
            onChange={(event) => {
              setDateTo(event.target.value);
              setPage(1);
            }}
          />
        </label>
        <label className="flex items-end gap-2 text-xs text-muted-foreground">
          <input
            type="checkbox"
            className="h-4 w-4"
            checked={includeArchived}
            onChange={(event) => {
              setIncludeArchived(event.target.checked);
              setPage(1);
            }}
          />
          Include archived
        </label>
      </section>

      {query.isLoading ? (
        <LoadingState label="Loading transactions" />
      ) : query.error ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      ) : transactions.length === 0 ? (
        <EmptyState
          icon={Wallet}
          title="No transactions yet"
          description="No transactions match the current filters. Create one to get started."
          actionLabel="New transaction"
        />
      ) : (
        <>
          <EmployeeTransactionsTable
            transactions={transactions}
            onEdit={openEdit}
            onArchive={handleArchive}
            archivingId={archiveMutation.isPending ? archiveMutation.variables ?? null : null}
          />
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-muted-foreground">
              Page {page} of {pageCount}
            </p>
            <div className="flex gap-2">
              <Button variant="secondary" disabled={page === 1} onClick={() => setPage((value) => Math.max(value - 1, 1))}>
                Previous
              </Button>
              <Button
                variant="secondary"
                disabled={page >= pageCount}
                onClick={() => setPage((value) => Math.min(value + 1, pageCount))}
              >
                Next
              </Button>
            </div>
          </div>
        </>
      )}

      <EmployeeTransactionDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        transaction={editing}
        onSaved={(message) => setSuccessMessage(message)}
      />
    </div>
  );
}
