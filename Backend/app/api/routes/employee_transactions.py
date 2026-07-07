"""Employee-linked transaction routes: CRUD, filtering, and role-based access.

All routes are mounted under the API root path (``/api/v1``). ``employee_id``
references ``users.id``. Access control lives in
``app.employee_transactions.service`` so these handlers stay thin.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.session import get_db_session
from app.employee_transactions import service
from app.schemas import (
    EmployeeTransactionCreate,
    EmployeeTransactionList,
    EmployeeTransactionOut,
    EmployeeTransactionUpdate,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/employee-transactions", tags=["employee-transactions"])


def _filters(
    status_filter: Optional[str] = Query(None, alias="status"),
    transaction_type: Optional[str] = Query(None, alias="type"),
    currency: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    min_amount: Optional[float] = Query(None, ge=0),
    max_amount: Optional[float] = Query(None, ge=0),
    search: Optional[str] = Query(None, max_length=100),
    include_archived: bool = Query(False),
) -> dict:
    return {
        "status_filter": status_filter,
        "transaction_type": transaction_type,
        "currency": currency,
        "date_from": date_from,
        "date_to": date_to,
        "min_amount": min_amount,
        "max_amount": max_amount,
        "search": search,
        "include_archived": include_archived,
    }


@router.post("", response_model=EmployeeTransactionOut, status_code=status.HTTP_201_CREATED)
async def create_employee_transaction(
    payload: EmployeeTransactionCreate,
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user),
):
    """Create a transaction for an employee.

    Validates that the employee exists (in ``users``). Non-managers may only
    create transactions for themselves.
    """
    return service.create_transaction(db, user, payload)


@router.get("", response_model=EmployeeTransactionList)
async def list_employee_transactions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    sort_by: str = Query("transaction_date"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    filters: dict = Depends(_filters),
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user),
):
    """List transactions across employees.

    Managers/partners/admins see everyone; other users are transparently scoped
    to their own transactions.
    """
    rows, total = service.list_transactions(
        db, user, skip=skip, limit=limit, sort_by=sort_by, sort_dir=sort_dir, filters=filters
    )
    return EmployeeTransactionList(
        total=total,
        skip=skip,
        limit=limit,
        transactions=[EmployeeTransactionOut.model_validate(row) for row in rows],
    )


@router.get("/employee/{employee_id}", response_model=EmployeeTransactionList)
async def list_transactions_for_employee(
    employee_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    sort_by: str = Query("transaction_date"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    filters: dict = Depends(_filters),
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user),
):
    """List a single employee's transactions (access-checked)."""
    rows, total = service.list_transactions(
        db,
        user,
        employee_id=employee_id,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_dir=sort_dir,
        filters=filters,
    )
    return EmployeeTransactionList(
        total=total,
        skip=skip,
        limit=limit,
        transactions=[EmployeeTransactionOut.model_validate(row) for row in rows],
    )


@router.get("/{transaction_id}", response_model=EmployeeTransactionOut)
async def get_employee_transaction(
    transaction_id: str,
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user),
):
    return service.get_transaction(db, user, transaction_id)


@router.put("/{transaction_id}", response_model=EmployeeTransactionOut)
async def update_employee_transaction(
    transaction_id: str,
    payload: EmployeeTransactionUpdate,
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user),
):
    return service.update_transaction(db, user, transaction_id, payload)


@router.delete("/{transaction_id}", response_model=EmployeeTransactionOut)
async def archive_employee_transaction(
    transaction_id: str,
    db: Session = Depends(get_db_session),
    user=Depends(get_current_user),
):
    """Soft-delete (archive) a transaction. The row is kept for auditability."""
    return service.archive_transaction(db, user, transaction_id)
