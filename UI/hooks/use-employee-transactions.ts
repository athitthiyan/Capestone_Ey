"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  archiveEmployeeTransaction,
  createEmployeeTransaction,
  getEmployeeTransactions,
  getEmployeeTransactionsByEmployee,
  updateEmployeeTransaction,
  type EmployeeTransactionFilters,
  type UpdateEmployeeTransactionInput,
} from "@/services/employee-transactions.service";

const rootKey = ["employee-transactions"] as const;

export function useEmployeeTransactions(filters: EmployeeTransactionFilters = {}, enabled = true) {
  return useQuery({
    queryKey: [...rootKey, "list", filters],
    queryFn: () => getEmployeeTransactions(filters),
    enabled,
  });
}

export function useEmployeeTransactionsByEmployee(
  employeeId: string | undefined,
  filters: EmployeeTransactionFilters = {},
) {
  return useQuery({
    queryKey: [...rootKey, "by-employee", employeeId, filters],
    queryFn: () => getEmployeeTransactionsByEmployee(employeeId as string, filters),
    enabled: Boolean(employeeId),
  });
}

function useInvalidateTransactions() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: rootKey });
}

export function useCreateEmployeeTransaction() {
  const invalidate = useInvalidateTransactions();
  return useMutation({
    mutationFn: createEmployeeTransaction,
    onSuccess: () => invalidate(),
  });
}

export function useUpdateEmployeeTransaction() {
  const invalidate = useInvalidateTransactions();
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: UpdateEmployeeTransactionInput }) =>
      updateEmployeeTransaction(id, input),
    onSuccess: () => invalidate(),
  });
}

export function useArchiveEmployeeTransaction() {
  const invalidate = useInvalidateTransactions();
  return useMutation({
    mutationFn: archiveEmployeeTransaction,
    onSuccess: () => invalidate(),
  });
}
