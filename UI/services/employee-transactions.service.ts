import { apiRequest } from "@/services/api";
import type {
  EmployeeTransaction,
  EmployeeTransactionList,
  EmployeeTransactionStatus,
  EmployeeTransactionType,
} from "@/types/domain";

type ApiEmployeeTransaction = {
  id: string;
  employee_id: string;
  transaction_type: EmployeeTransactionType;
  amount: number;
  currency: string;
  status: EmployeeTransactionStatus;
  description?: string | null;
  reference_id?: string | null;
  transaction_date: string;
  is_archived: boolean;
  created_at: string;
  updated_at?: string | null;
};

type ApiEmployeeTransactionList = {
  total: number;
  skip: number;
  limit: number;
  transactions: ApiEmployeeTransaction[];
};

export type EmployeeTransactionFilters = {
  employeeId?: string;
  status?: EmployeeTransactionStatus;
  type?: EmployeeTransactionType;
  currency?: string;
  dateFrom?: string;
  dateTo?: string;
  minAmount?: number;
  maxAmount?: number;
  search?: string;
  includeArchived?: boolean;
  skip?: number;
  limit?: number;
  sortBy?: "transaction_date" | "amount" | "created_at" | "status" | "transaction_type";
  sortDir?: "asc" | "desc";
};

export type CreateEmployeeTransactionInput = {
  employeeId: string;
  transactionType: EmployeeTransactionType;
  amount: number;
  currency: string;
  status: EmployeeTransactionStatus;
  description?: string;
  referenceId?: string;
  transactionDate?: string;
};

export type UpdateEmployeeTransactionInput = Partial<
  Omit<CreateEmployeeTransactionInput, "employeeId">
>;

function mapTransaction(row: ApiEmployeeTransaction): EmployeeTransaction {
  return {
    id: row.id,
    employeeId: row.employee_id,
    transactionType: row.transaction_type,
    amount: row.amount,
    currency: row.currency,
    status: row.status,
    description: row.description ?? null,
    referenceId: row.reference_id ?? null,
    transactionDate: row.transaction_date,
    isArchived: row.is_archived,
    createdAt: row.created_at,
    updatedAt: row.updated_at ?? null,
  };
}

function buildQuery(filters: EmployeeTransactionFilters): string {
  const params = new URLSearchParams();
  const set = (key: string, value: unknown) => {
    if (value !== undefined && value !== null && value !== "") {
      params.set(key, String(value));
    }
  };
  set("status", filters.status);
  set("type", filters.type);
  set("currency", filters.currency);
  set("date_from", filters.dateFrom);
  set("date_to", filters.dateTo);
  set("min_amount", filters.minAmount);
  set("max_amount", filters.maxAmount);
  set("search", filters.search);
  if (filters.includeArchived) set("include_archived", true);
  set("skip", filters.skip);
  set("limit", filters.limit);
  set("sort_by", filters.sortBy);
  set("sort_dir", filters.sortDir);
  const query = params.toString();
  return query ? `?${query}` : "";
}

async function fetchList(path: string, filters: EmployeeTransactionFilters): Promise<EmployeeTransactionList> {
  const response = await apiRequest<ApiEmployeeTransactionList>(`${path}${buildQuery(filters)}`);
  return { total: response.total, transactions: response.transactions.map(mapTransaction) };
}

export async function getEmployeeTransactions(
  filters: EmployeeTransactionFilters = {},
): Promise<EmployeeTransactionList> {
  return fetchList("/employee-transactions", filters);
}

export async function getEmployeeTransactionsByEmployee(
  employeeId: string,
  filters: EmployeeTransactionFilters = {},
): Promise<EmployeeTransactionList> {
  return fetchList(`/employee-transactions/employee/${encodeURIComponent(employeeId)}`, filters);
}

export async function getEmployeeTransaction(id: string): Promise<EmployeeTransaction> {
  const row = await apiRequest<ApiEmployeeTransaction>(`/employee-transactions/${encodeURIComponent(id)}`);
  return mapTransaction(row);
}

export async function createEmployeeTransaction(
  input: CreateEmployeeTransactionInput,
): Promise<EmployeeTransaction> {
  const row = await apiRequest<ApiEmployeeTransaction>("/employee-transactions", {
    method: "POST",
    body: JSON.stringify({
      employee_id: input.employeeId,
      transaction_type: input.transactionType,
      amount: input.amount,
      currency: input.currency,
      status: input.status,
      description: input.description || null,
      reference_id: input.referenceId || null,
      transaction_date: input.transactionDate || null,
    }),
  });
  return mapTransaction(row);
}

export async function updateEmployeeTransaction(
  id: string,
  input: UpdateEmployeeTransactionInput,
): Promise<EmployeeTransaction> {
  const body: Record<string, unknown> = {};
  if (input.transactionType !== undefined) body.transaction_type = input.transactionType;
  if (input.amount !== undefined) body.amount = input.amount;
  if (input.currency !== undefined) body.currency = input.currency;
  if (input.status !== undefined) body.status = input.status;
  if (input.description !== undefined) body.description = input.description || null;
  if (input.referenceId !== undefined) body.reference_id = input.referenceId || null;
  if (input.transactionDate !== undefined) body.transaction_date = input.transactionDate || null;

  const row = await apiRequest<ApiEmployeeTransaction>(`/employee-transactions/${encodeURIComponent(id)}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
  return mapTransaction(row);
}

export async function archiveEmployeeTransaction(id: string): Promise<EmployeeTransaction> {
  const row = await apiRequest<ApiEmployeeTransaction>(`/employee-transactions/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
  return mapTransaction(row);
}
