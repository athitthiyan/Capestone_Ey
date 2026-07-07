# Employee Transactions

**Added:** 2026-07-07. Store, fetch, display, filter, and manage financial
transactions linked to a specific employee via `employee_id`.

## Design decisions

- **`employee_id` references `users.id`.** The project has no separate `employees`
  table; `users` is the only person entity (with roles analyst/reviewer/partner/admin).
  The logged-in user *is* the employee, so "own transactions" and RBAC reuse the
  existing auth identity. (If audited staff later need to be separated from app users,
  add an `employees` table and repoint the FK - the API/UI stay the same.)
- **Dedicated `employee_transactions` table**, distinct from the audited general-ledger
  "transaction" concept (`investigations.transaction_id`).
- **Type/status stored as validated strings** (Pydantic `Literal`), matching
  `review_queue.status` and keeping the schema portable across SQLite and Postgres.
- **Delete = soft archive** (`is_archived=true`, `status="archived"`); rows are retained.

## Data model (`employee_transactions`)

| Column | Type | Notes |
|--------|------|-------|
| `id` | String(36) | UUID PK |
| `employee_id` | String(36) | FK -> `users.id` ON DELETE CASCADE, indexed |
| `transaction_type` | String(50) | credit/debit/reimbursement/payroll/bonus/deduction/adjustment |
| `amount` | Float | > 0 |
| `currency` | String(3) | ISO code, default `USD` |
| `status` | String(50) | pending/completed/failed/cancelled/archived |
| `description` | Text | optional |
| `reference_id` | String(100) | optional, indexed |
| `transaction_date` | DateTime | defaults to now |
| `is_archived` | Boolean | soft-delete flag |
| `created_at` / `updated_at` | DateTime | audit timestamps |

Indexes: `employee_id`, `status`, `transaction_type`, `transaction_date`, `reference_id`,
`is_archived`, plus composites `idx_emptx_employee_date` and `idx_emptx_status_type`.

## Authorization

| Role | Access |
|------|--------|
| manager / partner / admin | Read & manage **all** employees' transactions |
| any other authenticated user | Only their own (`employee_id == user.id`) |
| unauthenticated (`AUTH_REQUIRED=false`, dev) | Unrestricted |

Enforced in `app/employee_transactions/service.py` (`can_access_employee`,
`can_view_all_transactions`). Non-managers are transparently scoped to their own rows on
list endpoints; cross-employee access returns `403`. Creating for a non-existent employee
returns `404`.

## API examples

Create:

```bash
curl -X POST http://localhost:8000/api/v1/employee-transactions \
  -H "Content-Type: application/json" \
  -d '{
    "employee_id": "3f2c...-users-id",
    "transaction_type": "reimbursement",
    "amount": 249.50,
    "currency": "USD",
    "status": "pending",
    "description": "Client dinner",
    "reference_id": "REF-100"
  }'
```

Response `201`:

```json
{
  "id": "b71e...-tx-id",
  "employee_id": "3f2c...-users-id",
  "transaction_type": "reimbursement",
  "amount": 249.5,
  "currency": "USD",
  "status": "pending",
  "description": "Client dinner",
  "reference_id": "REF-100",
  "transaction_date": "2026-07-07T10:00:00",
  "is_archived": false,
  "created_at": "2026-07-07T10:00:00",
  "updated_at": "2026-07-07T10:00:00"
}
```

List one employee, filtered and paged:

```bash
curl "http://localhost:8000/api/v1/employee-transactions/employee/3f2c...-users-id?type=payroll&status=completed&min_amount=100&skip=0&limit=20&sort_by=amount&sort_dir=desc"
```

```json
{ "total": 2, "skip": 0, "limit": 20, "transactions": [ /* ... */ ] }
```

Update (partial) and archive:

```bash
curl -X PUT  .../employee-transactions/{id} -d '{"amount": 300.0, "status": "completed"}'
curl -X DELETE .../employee-transactions/{id}   # soft-archive
```

## Migration steps

```bash
cd Backend
alembic upgrade head        # applies 20260707_0005_add_employee_transactions
alembic current             # should report 20260707_0005
```

In dev/test the table is also created by `Base.metadata.create_all()` at startup.

## Local testing

```bash
cd Backend
pytest tests/test_employee_transactions.py -q
```

Covers: create with validation, invalid-employee `404`, CRUD + soft-archive, empty list,
type/amount filters, archived exclusion, and the RBAC scoping predicate.

## Frontend

- Page: **Employee transactions** (`/employee-transactions`, nav under "Results & setup").
- Files: `services/employee-transactions.service.ts`, `hooks/use-employee-transactions.ts`,
  `features/employee-transactions/employee-transactions-view.tsx`,
  `components/employee-transactions/{employee-transactions-table,employee-transaction-dialog}.tsx`.
- Features: filter by employee/search/status/type/date range/archived, sortable table with
  currency + date formatting and status badges, create/edit modal, soft-archive, and
  loading/empty/error/success states. The list auto-refreshes after create/update/archive
  via React Query invalidation of the `["employee-transactions"]` key.
