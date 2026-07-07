"""Tests for the employee-transactions feature.

The suite runs with AUTH_REQUIRED=false (see conftest), so the API behaves as an
unrestricted manager. Role-scoping logic is covered directly against the service
layer with AUTH_REQUIRED patched on.
"""

from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.core.security import can_view_all_transactions
from app.db.models import EmployeeTransaction, User
from app.employee_transactions import service
from app.schemas import EmployeeTransactionCreate


def _make_user(db, username, role="analyst"):
    user = User(username=username, hashed_password="x", role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# --------------------------------------------------------------------------- #
# API tests (AUTH_REQUIRED=false -> unrestricted)
# --------------------------------------------------------------------------- #

def test_create_requires_existing_employee(client):
    r = client.post(
        "/api/v1/employee-transactions",
        json={"employee_id": "does-not-exist", "amount": 100.0, "transaction_type": "payroll"},
    )
    assert r.status_code == 404, r.text


def test_create_validates_amount_and_type(client, db):
    emp = _make_user(db, "emp-validate")
    # amount must be > 0
    r = client.post(
        "/api/v1/employee-transactions",
        json={"employee_id": emp.id, "amount": 0, "transaction_type": "payroll"},
    )
    assert r.status_code == 422
    # transaction_type must be one of the allowed literals
    r = client.post(
        "/api/v1/employee-transactions",
        json={"employee_id": emp.id, "amount": 10, "transaction_type": "not-a-type"},
    )
    assert r.status_code == 422


def test_create_get_update_archive_flow(client, db):
    emp = _make_user(db, "emp-flow")
    create = client.post(
        "/api/v1/employee-transactions",
        json={
            "employee_id": emp.id,
            "transaction_type": "reimbursement",
            "amount": 249.5,
            "currency": "usd",
            "status": "pending",
            "description": "Client dinner",
            "reference_id": "REF-100",
        },
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["employee_id"] == emp.id
    assert body["currency"] == "USD"  # normalised to upper-case
    assert body["is_archived"] is False
    tx_id = body["id"]

    got = client.get(f"/api/v1/employee-transactions/{tx_id}")
    assert got.status_code == 200
    assert got.json()["reference_id"] == "REF-100"

    updated = client.put(
        f"/api/v1/employee-transactions/{tx_id}",
        json={"amount": 300.0, "status": "completed"},
    )
    assert updated.status_code == 200
    assert updated.json()["amount"] == 300.0
    assert updated.json()["status"] == "completed"

    archived = client.delete(f"/api/v1/employee-transactions/{tx_id}")
    assert archived.status_code == 200
    assert archived.json()["is_archived"] is True
    assert archived.json()["status"] == "archived"


def test_get_missing_returns_404(client):
    r = client.get("/api/v1/employee-transactions/nope")
    assert r.status_code == 404


def test_list_by_employee_and_filters(client, db):
    emp = _make_user(db, "emp-list")
    for i in range(3):
        client.post(
            "/api/v1/employee-transactions",
            json={
                "employee_id": emp.id,
                "amount": 100 + i,
                "transaction_type": "payroll" if i < 2 else "bonus",
                "status": "completed",
            },
        )
    listed = client.get(f"/api/v1/employee-transactions/employee/{emp.id}")
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 3
    assert len(body["transactions"]) == 3

    # filter by type
    payroll = client.get(f"/api/v1/employee-transactions/employee/{emp.id}?type=payroll")
    assert payroll.json()["total"] == 2

    # amount range filter
    ranged = client.get(
        f"/api/v1/employee-transactions/employee/{emp.id}?min_amount=101&max_amount=101"
    )
    assert ranged.json()["total"] == 1


def test_empty_list_for_employee_with_no_transactions(client, db):
    emp = _make_user(db, "emp-empty")
    r = client.get(f"/api/v1/employee-transactions/employee/{emp.id}")
    assert r.status_code == 200
    assert r.json()["total"] == 0
    assert r.json()["transactions"] == []


def test_archived_excluded_unless_requested(client, db):
    emp = _make_user(db, "emp-archived")
    created = client.post(
        "/api/v1/employee-transactions",
        json={"employee_id": emp.id, "amount": 50, "transaction_type": "adjustment"},
    ).json()
    client.delete(f"/api/v1/employee-transactions/{created['id']}")

    default = client.get(f"/api/v1/employee-transactions/employee/{emp.id}")
    assert default.json()["total"] == 0
    with_archived = client.get(
        f"/api/v1/employee-transactions/employee/{emp.id}?include_archived=true"
    )
    assert with_archived.json()["total"] == 1


# --------------------------------------------------------------------------- #
# RBAC unit tests (AUTH_REQUIRED patched on)
# --------------------------------------------------------------------------- #

@pytest.fixture()
def auth_on(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_REQUIRED", True)
    yield


def test_can_view_all_transactions_by_role(auth_on):
    assert can_view_all_transactions(None) is False
    assert can_view_all_transactions(SimpleNamespace(role="admin", id="u1")) is True
    assert can_view_all_transactions(SimpleNamespace(role="partner", id="u1")) is True
    assert can_view_all_transactions(SimpleNamespace(role="manager", id="u1")) is True
    assert can_view_all_transactions(SimpleNamespace(role="analyst", id="u1")) is False


def test_can_access_employee_own_only(auth_on):
    analyst = SimpleNamespace(role="analyst", id="u1")
    assert service.can_access_employee(analyst, "u1") is True
    assert service.can_access_employee(analyst, "u2") is False
    manager = SimpleNamespace(role="manager", id="u1")
    assert service.can_access_employee(manager, "u2") is True


def test_non_manager_list_is_scoped_to_own(auth_on, db):
    emp_a = _make_user(db, "scope-a", role="analyst")
    emp_b = _make_user(db, "scope-b", role="analyst")
    for emp in (emp_a, emp_b):
        service.create_transaction(
            db,
            None if False else SimpleNamespace(role="manager", id="mgr"),
            EmployeeTransactionCreate(employee_id=emp.id, amount=10, transaction_type="payroll"),
        )
    rows, total = service.list_transactions(db, SimpleNamespace(role="analyst", id=emp_a.id))
    assert total == 1
    assert all(isinstance(r, EmployeeTransaction) for r in rows)
    assert rows[0].employee_id == emp_a.id


def test_delete_all_wipes_transactions_but_preserves_users(client, db):
    from app.db.models import EmployeeTransaction, Investigation, User

    emp = _make_user(db, "wipe-user")
    client.post(
        "/api/v1/employee-transactions",
        json={"employee_id": emp.id, "amount": 42, "transaction_type": "bonus"},
    )
    client.post(
        "/api/v1/investigations",
        json={"transaction_id": "TXN-WIPE", "vendor": "V", "category": "c", "amount": 100.0},
    )
    assert db.query(EmployeeTransaction).count() >= 1

    r = client.delete("/api/v1/investigations/all")
    assert r.status_code == 200, r.text

    db.expire_all()
    # Business + telemetry data is gone...
    assert db.query(Investigation).count() == 0
    assert db.query(EmployeeTransaction).count() == 0
    # ...but the user (account) is preserved.
    assert db.query(User).filter(User.id == emp.id).count() == 1
