"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  useCreateEmployeeTransaction,
  useUpdateEmployeeTransaction,
} from "@/hooks/use-employee-transactions";
import { ApiError } from "@/services/api";
import type {
  EmployeeTransaction,
  EmployeeTransactionStatus,
  EmployeeTransactionType,
} from "@/types/domain";

const TYPES: EmployeeTransactionType[] = [
  "credit",
  "debit",
  "reimbursement",
  "payroll",
  "bonus",
  "deduction",
  "adjustment",
];
const STATUSES: EmployeeTransactionStatus[] = ["pending", "completed", "failed", "cancelled", "archived"];

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** null = create, otherwise edit. */
  transaction: EmployeeTransaction | null;
  onSaved: (message: string) => void;
};

type FormState = {
  employeeId: string;
  transactionType: EmployeeTransactionType;
  amount: string;
  currency: string;
  status: EmployeeTransactionStatus;
  referenceId: string;
  description: string;
  transactionDate: string;
};

const emptyForm: FormState = {
  employeeId: "",
  transactionType: "debit",
  amount: "",
  currency: "USD",
  status: "pending",
  referenceId: "",
  description: "",
  transactionDate: "",
};

function toDateInput(value?: string | null) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toISOString().slice(0, 10);
}

export function EmployeeTransactionDialog({ open, onOpenChange, transaction, onSaved }: Props) {
  const isEdit = Boolean(transaction);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [error, setError] = useState<string | null>(null);
  const createMutation = useCreateEmployeeTransaction();
  const updateMutation = useUpdateEmployeeTransaction();
  const submitting = createMutation.isPending || updateMutation.isPending;

  useEffect(() => {
    if (!open) return;
    setError(null);
    setForm(
      transaction
        ? {
            employeeId: transaction.employeeId,
            transactionType: transaction.transactionType,
            amount: String(transaction.amount),
            currency: transaction.currency,
            status: transaction.status,
            referenceId: transaction.referenceId ?? "",
            description: transaction.description ?? "",
            transactionDate: toDateInput(transaction.transactionDate),
          }
        : emptyForm,
    );
  }, [open, transaction]);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);

    const amount = Number(form.amount);
    if (!Number.isFinite(amount) || amount <= 0) {
      setError("Amount must be a number greater than zero.");
      return;
    }
    if (!isEdit && !form.employeeId.trim()) {
      setError("Employee ID is required.");
      return;
    }

    const transactionDate = form.transactionDate
      ? new Date(form.transactionDate).toISOString()
      : undefined;

    try {
      if (isEdit && transaction) {
        await updateMutation.mutateAsync({
          id: transaction.id,
          input: {
            transactionType: form.transactionType,
            amount,
            currency: form.currency.toUpperCase(),
            status: form.status,
            referenceId: form.referenceId,
            description: form.description,
            transactionDate,
          },
        });
        onSaved("Transaction updated.");
      } else {
        await createMutation.mutateAsync({
          employeeId: form.employeeId.trim(),
          transactionType: form.transactionType,
          amount,
          currency: form.currency.toUpperCase(),
          status: form.status,
          referenceId: form.referenceId,
          description: form.description,
          transactionDate,
        });
        onSaved("Transaction created.");
      }
      onOpenChange(false);
    } catch (submitError) {
      setError(
        submitError instanceof ApiError
          ? submitError.message
          : "Could not save the transaction. Please try again.",
      );
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/50" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 max-h-[90vh] w-full max-w-lg -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-lg border border-border bg-card p-6 shadow-panel">
          <Dialog.Title className="text-base font-semibold text-foreground">
            {isEdit ? "Edit transaction" : "New transaction"}
          </Dialog.Title>
          <Dialog.Description className="mt-1 text-sm text-muted-foreground">
            {isEdit
              ? "Update the details of this employee transaction."
              : "Record a transaction for an employee. The employee must exist."}
          </Dialog.Description>

          <form className="mt-4 grid gap-3 sm:grid-cols-2" onSubmit={handleSubmit}>
            <label className="text-xs text-muted-foreground sm:col-span-2">
              Employee ID
              <Input
                className="mt-1"
                value={form.employeeId}
                disabled={isEdit}
                placeholder="users.id of the employee"
                onChange={(event) => update("employeeId", event.target.value)}
              />
            </label>

            <label className="text-xs text-muted-foreground">
              Type
              <select
                className="mt-1 h-9 w-full rounded-md border border-input bg-background px-3 text-sm text-foreground"
                value={form.transactionType}
                onChange={(event) => update("transactionType", event.target.value as EmployeeTransactionType)}
              >
                {TYPES.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </select>
            </label>

            <label className="text-xs text-muted-foreground">
              Status
              <select
                className="mt-1 h-9 w-full rounded-md border border-input bg-background px-3 text-sm text-foreground"
                value={form.status}
                onChange={(event) => update("status", event.target.value as EmployeeTransactionStatus)}
              >
                {STATUSES.map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </select>
            </label>

            <label className="text-xs text-muted-foreground">
              Amount
              <Input
                className="mt-1"
                type="number"
                min="0"
                step="0.01"
                value={form.amount}
                onChange={(event) => update("amount", event.target.value)}
              />
            </label>

            <label className="text-xs text-muted-foreground">
              Currency
              <Input
                className="mt-1"
                maxLength={3}
                value={form.currency}
                onChange={(event) => update("currency", event.target.value)}
              />
            </label>

            <label className="text-xs text-muted-foreground">
              Reference ID
              <Input
                className="mt-1"
                value={form.referenceId}
                onChange={(event) => update("referenceId", event.target.value)}
              />
            </label>

            <label className="text-xs text-muted-foreground">
              Transaction date
              <Input
                className="mt-1"
                type="date"
                value={form.transactionDate}
                onChange={(event) => update("transactionDate", event.target.value)}
              />
            </label>

            <label className="text-xs text-muted-foreground sm:col-span-2">
              Description
              <Textarea
                className="mt-1 min-h-20"
                value={form.description}
                onChange={(event) => update("description", event.target.value)}
              />
            </label>

            {error ? (
              <p className="sm:col-span-2 rounded-md border border-danger-border bg-danger-soft px-3 py-2 text-xs text-danger-foreground">
                {error}
              </p>
            ) : null}

            <div className="sm:col-span-2 mt-1 flex justify-end gap-2">
              <Dialog.Close asChild>
                <Button type="button" variant="secondary" disabled={submitting}>
                  Cancel
                </Button>
              </Dialog.Close>
              <Button type="submit" disabled={submitting}>
                {submitting ? "Saving…" : isEdit ? "Save changes" : "Create transaction"}
              </Button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
