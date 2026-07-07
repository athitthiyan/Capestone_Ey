"""Business logic for employee-linked transactions.

Access rules (enforced here so routes stay thin and the logic is unit-testable):

* When ``AUTH_REQUIRED`` is false (dev/tests) access is unrestricted, matching
  the rest of the app.
* Managers/partners/admins may read and manage every employee's transactions.
* Everyone else may only read and manage their own (``employee_id == user.id``).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Query, Session

from app.core.security import can_view_all_transactions
from app.db.models import EmployeeTransaction, User
from app.schemas import EmployeeTransactionCreate, EmployeeTransactionUpdate

# Whitelisted sort columns; anything else falls back to transaction_date.
_SORTABLE = {
    "transaction_date": EmployeeTransaction.transaction_date,
    "amount": EmployeeTransaction.amount,
    "created_at": EmployeeTransaction.created_at,
    "updated_at": EmployeeTransaction.updated_at,
    "status": EmployeeTransaction.status,
    "transaction_type": EmployeeTransaction.transaction_type,
}


def _current_user_id(user: Optional[User]) -> Optional[str]:
    return getattr(user, "id", None)


def can_access_employee(user: Optional[User], employee_id: str) -> bool:
    """Pure predicate: may this user read/manage transactions for employee_id."""
    if can_view_all_transactions(user):
        return True
    return _current_user_id(user) == employee_id


def _assert_access(user: Optional[User], employee_id: str) -> None:
    if not can_access_employee(user, employee_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own transactions.",
        )


def employee_exists(db: Session, employee_id: str) -> bool:
    return db.query(User.id).filter(User.id == employee_id).first() is not None


def _resolve_create_employee_id(
    db: Session, user: Optional[User], requested: Optional[str]
) -> str:
    target = requested or _current_user_id(user)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="employee_id is required when there is no authenticated user.",
        )
    if not can_access_employee(user, target):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create transactions for yourself.",
        )
    if not employee_exists(db, target):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee '{target}' was not found.",
        )
    return target


def create_transaction(
    db: Session, user: Optional[User], data: EmployeeTransactionCreate
) -> EmployeeTransaction:
    employee_id = _resolve_create_employee_id(db, user, data.employee_id)
    transaction = EmployeeTransaction(
        employee_id=employee_id,
        transaction_type=data.transaction_type,
        amount=data.amount,
        currency=data.currency,
        status=data.status,
        description=data.description,
        reference_id=data.reference_id,
        transaction_date=data.transaction_date or datetime.utcnow(),
        is_archived=(data.status == "archived"),
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


def _filtered_query(
    db: Session,
    *,
    employee_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    transaction_type: Optional[str] = None,
    currency: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    search: Optional[str] = None,
    include_archived: bool = False,
) -> Query:
    query = db.query(EmployeeTransaction)
    if employee_id:
        query = query.filter(EmployeeTransaction.employee_id == employee_id)
    if not include_archived:
        query = query.filter(EmployeeTransaction.is_archived.is_(False))
    if status_filter:
        query = query.filter(EmployeeTransaction.status == status_filter)
    if transaction_type:
        query = query.filter(EmployeeTransaction.transaction_type == transaction_type)
    if currency:
        query = query.filter(EmployeeTransaction.currency == currency.upper())
    if date_from:
        query = query.filter(EmployeeTransaction.transaction_date >= date_from)
    if date_to:
        query = query.filter(EmployeeTransaction.transaction_date <= date_to)
    if min_amount is not None:
        query = query.filter(EmployeeTransaction.amount >= min_amount)
    if max_amount is not None:
        query = query.filter(EmployeeTransaction.amount <= max_amount)
    if search and search.strip():
        like = f"%{search.strip()}%"
        query = query.filter(
            or_(
                EmployeeTransaction.description.ilike(like),
                EmployeeTransaction.reference_id.ilike(like),
            )
        )
    return query


def list_transactions(
    db: Session,
    user: Optional[User],
    *,
    employee_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    sort_by: str = "transaction_date",
    sort_dir: str = "desc",
    filters: Optional[dict] = None,
) -> tuple[list[EmployeeTransaction], int]:
    filters = filters or {}

    # Scope non-managers to their own rows regardless of the requested employee_id.
    if not can_view_all_transactions(user):
        own = _current_user_id(user)
        if employee_id and employee_id != own:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own transactions.",
            )
        employee_id = own
        if not employee_id:
            return [], 0

    query = _filtered_query(db, employee_id=employee_id, **filters)
    total = query.with_entities(func.count(EmployeeTransaction.id)).scalar() or 0

    column = _SORTABLE.get(sort_by, EmployeeTransaction.transaction_date)
    column = column.asc() if sort_dir == "asc" else column.desc()
    limit = max(1, min(limit, 200))
    rows = (
        query.order_by(column, EmployeeTransaction.id.desc())
        .offset(max(skip, 0))
        .limit(limit)
        .all()
    )
    return rows, total


def get_transaction(db: Session, user: Optional[User], transaction_id: str) -> EmployeeTransaction:
    transaction = db.get(EmployeeTransaction, transaction_id)
    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found."
        )
    _assert_access(user, transaction.employee_id)
    return transaction


def update_transaction(
    db: Session, user: Optional[User], transaction_id: str, data: EmployeeTransactionUpdate
) -> EmployeeTransaction:
    transaction = get_transaction(db, user, transaction_id)
    payload = data.model_dump(exclude_unset=True)
    if payload.get("currency"):
        payload["currency"] = payload["currency"].upper()
    for field, value in payload.items():
        setattr(transaction, field, value)
    if "status" in payload:
        transaction.is_archived = payload["status"] == "archived"
    db.commit()
    db.refresh(transaction)
    return transaction


def archive_transaction(
    db: Session, user: Optional[User], transaction_id: str
) -> EmployeeTransaction:
    """Soft-delete: mark archived rather than physically removing the row."""
    transaction = get_transaction(db, user, transaction_id)
    transaction.is_archived = True
    transaction.status = "archived"
    db.commit()
    db.refresh(transaction)
    return transaction
