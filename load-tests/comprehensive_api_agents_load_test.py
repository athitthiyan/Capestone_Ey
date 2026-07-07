"""Comprehensive API + agent workflow load test for Skeptic Engine.

This runner intentionally uses only the Python standard library so it can run
anywhere the backend repo can run. It exercises the public API surface,
triggers the investigation agent crew, and validates the Prometheus/analytics
signals after the run.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
import json
import os
import random
import statistics
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TERMINAL_STATUSES = {"human_review", "report_ready", "closed", "failed"}
REPORTS_DIR = Path(__file__).resolve().parent / "reports"


@dataclasses.dataclass
class ApiResult:
    method: str
    path: str
    status: int
    ok: bool
    duration_ms: float
    name: str
    error: str | None = None


@dataclasses.dataclass
class ScenarioResult:
    created_case_ids: list[str]
    executed_case_ids: list[str]
    terminal_case_ids: list[str]
    employee_transaction_ids: list[str]
    employee_transaction_skips: list[dict[str, Any]]
    case_observability: dict[str, dict[str, Any]]
    results: list[ApiResult]


class ApiClient:
    def __init__(
        self,
        base_url: str,
        *,
        token: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        parsed = urllib.parse.urlparse(self.base_url)
        if parsed.path.endswith("/api/v1"):
            root_path = parsed.path[: -len("/api/v1")] or "/"
            self.root_url = urllib.parse.urlunparse(parsed._replace(path=root_path.rstrip("/")))
        else:
            self.root_url = urllib.parse.urlunparse(parsed._replace(path=""))
        self.timeout = timeout
        self.token = token
        self.results: list[ApiResult] = []
        self.lock = threading.Lock()

    def set_token(self, token: str | None) -> None:
        self.token = token

    def _url(self, path: str, *, root: bool = False) -> str:
        base = self.root_url if root else self.base_url
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return f"{base}/{path.lstrip('/')}"

    def request(
        self,
        method: str,
        path: str,
        *,
        name: str | None = None,
        json_body: Any | None = None,
        form_body: dict[str, str] | None = None,
        query: dict[str, Any] | None = None,
        root: bool = False,
        expected: set[int] | None = None,
        auth: bool = True,
    ) -> tuple[int, Any, ApiResult]:
        expected = expected or {200}
        url = self._url(path, root=root)
        if query:
            encoded = urllib.parse.urlencode(
                {key: value for key, value in query.items() if value is not None}
            )
            url = f"{url}?{encoded}"

        headers = {"Accept": "application/json"}
        data: bytes | None = None
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif form_body is not None:
            data = urllib.parse.urlencode(form_body).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"

        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        started = time.perf_counter()
        status = 0
        payload: Any = None
        error: str | None = None
        try:
            request = urllib.request.Request(url, data=data, headers=headers, method=method)
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                status = response.getcode()
                raw = response.read()
                payload = self._parse_payload(raw, response.headers.get("Content-Type", ""))
        except urllib.error.HTTPError as exc:
            status = exc.code
            raw = exc.read()
            payload = self._parse_payload(raw, exc.headers.get("Content-Type", ""))
            error = self._detail(payload) or str(exc)
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
        duration_ms = (time.perf_counter() - started) * 1000
        result = ApiResult(
            method=method,
            path=path,
            status=status,
            ok=status in expected,
            duration_ms=duration_ms,
            name=name or f"{method} {path}",
            error=error,
        )
        with self.lock:
            self.results.append(result)
        return status, payload, result

    @staticmethod
    def _parse_payload(raw: bytes, content_type: str) -> Any:
        if not raw:
            return None
        text = raw.decode("utf-8", errors="replace")
        if "application/json" in content_type:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
        return text

    @staticmethod
    def _detail(payload: Any) -> str | None:
        if isinstance(payload, dict) and "detail" in payload:
            return str(payload["detail"])
        return None


class LoadTest:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        self.agent_budget = args.agent_cases
        self.agent_budget_lock = threading.Lock()
        self.employee_id: str | None = None
        self.client = ApiClient(
            args.base_url,
            token=args.token,
            timeout=args.timeout,
        )
        self.metrics_before: dict[str, float] = {}
        self.metrics_after: dict[str, float] = {}
        self.analytics_before: dict[str, Any] = {}
        self.analytics_after: dict[str, Any] = {}
        self.validation_failures: list[str] = []
        self.validation_warnings: list[str] = []

    def run(self) -> int:
        started = time.perf_counter()
        self.authenticate_or_register_employee()
        self.capture_before()
        self.prime_shared_endpoints()

        scenario_results: list[ScenarioResult] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.args.users) as executor:
            futures = [
                executor.submit(self.run_iteration, iteration)
                for iteration in range(self.args.iterations)
            ]
            for future in concurrent.futures.as_completed(futures):
                scenario_results.append(future.result())

        self.capture_after()
        report = self.build_report(scenario_results, time.perf_counter() - started)
        self.validate(report)
        self.write_report(report)
        self.print_summary(report)
        return 1 if self.validation_failures else 0

    def authenticate_or_register_employee(self) -> None:
        username = self.args.username or f"loadtest-{self.run_id}"
        password = self.args.password or f"LoadTest-{self.run_id}-password"

        if self.args.token:
            self.client.set_token(self.args.token)

        if self.args.username and self.args.password and not self.args.token:
            _status, payload, _result = self.client.request(
                "POST",
                "/auth/token",
                name="auth.token",
                form_body={"username": username, "password": password},
                expected={200, 401},
                auth=False,
            )
            if isinstance(payload, dict) and payload.get("access_token"):
                self.client.set_token(str(payload["access_token"]))

        status, payload, _result = self.client.request(
            "POST",
            "/auth/register",
            name="auth.register.load_user",
            json_body={
                "username": username,
                "password": password,
                "email": f"{username}@loadtest.local",
                "role": "analyst",
            },
            expected={201, 409, 429},
            auth=False,
        )
        if status == 201 and isinstance(payload, dict):
            self.employee_id = str(payload.get("id") or "")
            token_status, token_payload, _ = self.client.request(
                "POST",
                "/auth/token",
                name="auth.token.load_user",
                form_body={"username": username, "password": password},
                expected={200, 401, 429},
                auth=False,
            )
            if token_status == 200 and isinstance(token_payload, dict):
                self.client.set_token(token_payload.get("access_token"))
        elif self.client.token:
            status, payload, _result = self.client.request(
                "GET",
                "/auth/me",
                name="auth.me",
                expected={200, 401},
            )
            if status == 200 and isinstance(payload, dict):
                self.employee_id = str(payload.get("id") or "")

    def capture_before(self) -> None:
        self.metrics_before = self.fetch_prometheus_metrics()
        _status, payload, _ = self.client.request(
            "GET",
            "/analytics/requests",
            name="analytics.requests.before",
            query={"limit": 1000},
            expected={200},
        )
        self.analytics_before["requests"] = payload
        _status, payload, _ = self.client.request(
            "GET",
            "/analytics/llm/summary",
            name="analytics.llm.summary.before",
            expected={200},
        )
        self.analytics_before["llm_summary"] = payload

    def capture_after(self) -> None:
        self.metrics_after = self.fetch_prometheus_metrics()
        for name, path in [
            ("requests", "/analytics/requests"),
            ("llm_summary", "/analytics/llm/summary"),
            ("llm_by_provider", "/analytics/llm/by-provider"),
            ("llm_by_model", "/analytics/llm/by-model"),
            ("llm_recent_calls", "/analytics/llm/recent-calls"),
            ("llm_cost_trends", "/analytics/llm/cost-trends"),
        ]:
            _status, payload, _ = self.client.request(
                "GET",
                path,
                name=f"analytics.{name}.after",
                query={"limit": 1000} if name in {"requests", "llm_recent_calls"} else None,
                expected={200},
            )
            self.analytics_after[name] = payload

    def prime_shared_endpoints(self) -> None:
        for name, method, path, kwargs in [
            ("health.root", "GET", "/health", {"root": True}),
            ("health.detailed", "GET", "/health/detailed", {"root": True}),
            ("settings.get", "GET", "/settings", {}),
            ("settings.llm", "GET", "/settings/llm", {}),
            ("settings.llm.providers", "GET", "/settings/llm/providers", {}),
            ("knowledge.sources", "GET", "/knowledge/sources", {}),
            ("knowledge.chunks", "GET", "/knowledge/chunks", {}),
            (
                "knowledge.search",
                "GET",
                "/knowledge/search",
                {"query": {"q": "materiality approval vendor policy", "limit": 5}},
            ),
            ("knowledge.reindex", "POST", "/knowledge/reindex", {}),
            ("audit.recent", "GET", "/audit/recent", {}),
            ("evaluation.summary", "GET", "/evaluation/summary", {}),
            ("evaluation.metrics", "GET", "/evaluation/metrics", {}),
            ("evaluation.by_llm", "GET", "/evaluation/by-llm", {}),
            ("agents.health", "GET", "/agents/health", {}),
            ("reports.list", "GET", "/reports", {}),
            ("reviews.queue", "GET", "/reviews/queue", {}),
            ("intake.summary", "GET", "/intake/summary", {"expected": {200, 404}}),
        ]:
            expected = kwargs.pop("expected", {200})
            self.client.request(method, path, name=name, expected=expected, **kwargs)

    def run_iteration(self, iteration: int) -> ScenarioResult:
        local = ApiClient(
            self.args.base_url,
            token=self.client.token,
            timeout=self.args.timeout,
        )
        created_case_ids: list[str] = []
        executed_case_ids: list[str] = []
        terminal_case_ids: list[str] = []
        employee_transaction_ids: list[str] = []
        employee_transaction_skips: list[dict[str, Any]] = []
        case_observability: dict[str, dict[str, Any]] = {}

        case_id = self.create_investigation(local, iteration)
        if case_id:
            created_case_ids.append(case_id)
            self.exercise_case_read_apis(local, case_id)
            self.exercise_claim_apis(local, case_id)
            if self.claim_agent_budget():
                executed_case_ids.append(case_id)
                self.execute_case(local, case_id)
                if self.poll_case_terminal(local, case_id):
                    terminal_case_ids.append(case_id)
                self.exercise_case_read_apis(local, case_id)
                self.exercise_post_execution_apis(local, case_id)
                case_observability[case_id] = self.collect_case_observability(
                    local, case_id
                )
            else:
                self.exercise_review_apis(local, case_id)

        tx_id, tx_skip = self.exercise_employee_transaction_apis(local, iteration)
        if tx_id:
            employee_transaction_ids.append(tx_id)
        if tx_skip:
            employee_transaction_skips.append(tx_skip)

        self.exercise_analytics_apis(local)

        with self.client.lock:
            self.client.results.extend(local.results)

        return ScenarioResult(
            created_case_ids=created_case_ids,
            executed_case_ids=executed_case_ids,
            terminal_case_ids=terminal_case_ids,
            employee_transaction_ids=employee_transaction_ids,
            employee_transaction_skips=employee_transaction_skips,
            case_observability=case_observability,
            results=local.results,
        )

    def create_investigation(self, client: ApiClient, iteration: int) -> str | None:
        amount = random.choice([1200.0, 17500.0, 76000.0, 125000.0])
        payload = {
            "transaction_id": f"LOAD-{self.run_id}-{iteration}",
            "vendor": f"Load Test Vendor {iteration}",
            "category": random.choice(["consulting", "travel", "software", "fuel"]),
            "amount": amount,
            "materiality": 50000.0,
            "description": "Load-test investigation covering API and agent workflow.",
            "owner": "load-test",
        }
        status, body, _ = client.request(
            "POST",
            "/investigations",
            name="investigations.create",
            json_body=payload,
            expected={201},
        )
        if status == 201 and isinstance(body, dict):
            return str(body.get("id") or "")
        return None

    def exercise_case_read_apis(self, client: ApiClient, case_id: str) -> None:
        for name, path, expected in [
            ("investigations.list", "/investigations", {200}),
            ("investigations.stats", "/investigations/stats/summary", {200}),
            ("investigations.get", f"/investigations/{case_id}", {200}),
            ("investigations.workspace", f"/investigations/{case_id}/workspace", {200}),
            ("investigations.debate", f"/investigations/{case_id}/debate", {200}),
            ("investigations.evidence", f"/investigations/{case_id}/evidence", {200}),
            ("investigations.verification", f"/investigations/{case_id}/verification", {200}),
            ("investigations.audit", f"/investigations/{case_id}/audit", {200}),
            ("investigations.replay", f"/investigations/{case_id}/replay", {200}),
            ("agents.workflow", f"/agents/workflow/{case_id}", {200}),
            ("evaluation.case", f"/evaluation/case/{case_id}", {200}),
            ("reports.by_case", "/reports", {200}),
        ]:
            query = {"investigation_id": case_id} if name == "reports.by_case" else None
            client.request("GET", path, name=name, expected=expected, query=query)

    def exercise_claim_apis(self, client: ApiClient, case_id: str) -> None:
        preview_payload = {
            "category": "fuel",
            "claimed_amount": 1050.0,
            "quantity": 10.0,
            "currency": "INR",
            "location": "Puducherry",
        }
        client.request(
            "POST",
            "/claims/verify-preview",
            name="claims.verify_preview",
            json_body=preview_payload,
            expected={200},
        )
        client.request(
            "POST",
            f"/claims/{case_id}/verify-evidence",
            name="claims.verify_evidence",
            json_body=preview_payload,
            expected={201},
        )
        client.request(
            "GET",
            f"/claims/{case_id}/verification",
            name="claims.verification",
            expected={200},
        )

    def claim_agent_budget(self) -> bool:
        if self.args.skip_agent_execution:
            return False
        with self.agent_budget_lock:
            if self.agent_budget <= 0:
                return False
            self.agent_budget -= 1
            return True

    def execute_case(self, client: ApiClient, case_id: str) -> None:
        client.request(
            "POST",
            f"/investigations/{case_id}/execute",
            name="investigations.execute",
            expected={200},
        )

    def poll_case_terminal(self, client: ApiClient, case_id: str) -> bool:
        deadline = time.monotonic() + self.args.poll_timeout
        while time.monotonic() < deadline:
            status, payload, _ = client.request(
                "GET",
                f"/investigations/{case_id}",
                name="investigations.poll",
                expected={200},
            )
            if status == 200 and isinstance(payload, dict):
                if str(payload.get("status")) in TERMINAL_STATUSES:
                    return True
            time.sleep(self.args.poll_interval)
        return False

    def exercise_post_execution_apis(self, client: ApiClient, case_id: str) -> None:
        status, payload, _ = client.request(
            "GET",
            f"/investigations/{case_id}",
            name="investigations.after_execute",
            expected={200},
        )
        case_status = str(payload.get("status")) if isinstance(payload, dict) else ""
        if case_status == "human_review":
            client.request(
                "POST",
                f"/reviews/{case_id}/approve",
                name="reviews.approve",
                json_body={
                    "actor": "load-test",
                    "comment": "Approved by load test after exercising agent workflow.",
                    "ground_truth": "The transaction was reviewed and accepted for load-test purposes.",
                },
            expected={200},
        )
        client.request("GET", "/reports", name="reports.list.after_execute", expected={200})

    def collect_case_observability(
        self, client: ApiClient, case_id: str
    ) -> dict[str, Any]:
        observation: dict[str, Any] = {
            "status": None,
            "evidence_count": 0,
            "debate_count": 0,
            "verification_count": 0,
            "has_evidence_verification": False,
            "has_evaluation": False,
            "workflow_step_count": 0,
            "workflow_done_steps": 0,
            "workflow_running_steps": 0,
            "workflow_failed_steps": 0,
            "workflow_states": {},
        }

        status, payload, _ = client.request(
            "GET",
            f"/investigations/{case_id}",
            name="observability.investigation",
            expected={200},
        )
        if status == 200 and isinstance(payload, dict):
            observation["status"] = payload.get("status")

        workspace_status, workspace, _ = client.request(
            "GET",
            f"/investigations/{case_id}/workspace",
            name="observability.workspace",
            expected={200},
        )
        if workspace_status == 200 and isinstance(workspace, dict):
            investigation = workspace.get("investigation")
            if isinstance(investigation, dict) and not observation["status"]:
                observation["status"] = investigation.get("status")
            for key in ("evidence", "debate", "verification"):
                rows = workspace.get(key)
                if isinstance(rows, list):
                    observation[f"{key}_count"] = len(rows)
            observation["has_evidence_verification"] = bool(
                workspace.get("evidence_verification")
            )
            observation["has_evaluation"] = isinstance(workspace.get("evaluation"), dict)

        workflow_status, workflow, _ = client.request(
            "GET",
            f"/agents/workflow/{case_id}",
            name="observability.workflow",
            expected={200},
        )
        if workflow_status == 200 and isinstance(workflow, list):
            states = Counter(
                str(step.get("state") or "")
                for step in workflow
                if isinstance(step, dict)
            )
            observation["workflow_step_count"] = len(workflow)
            observation["workflow_done_steps"] = states.get("done", 0)
            observation["workflow_running_steps"] = states.get("running", 0)
            observation["workflow_failed_steps"] = states.get("failed", 0)
            observation["workflow_states"] = dict(sorted(states.items()))

        return observation

    def exercise_review_apis(self, client: ApiClient, case_id: str) -> None:
        client.request(
            "POST",
            f"/reviews/{case_id}/escalate",
            name="reviews.escalate",
            json_body={"actor": "load-test", "comment": "Load-test escalation path."},
            expected={200},
        )
        client.request("GET", "/reviews/queue", name="reviews.queue.after_escalate", expected={200})
        client.request(
            "POST",
            f"/reviews/{case_id}/request-evidence",
            name="reviews.request_evidence",
            json_body={"actor": "load-test", "comment": "Load-test evidence request path."},
            expected={200},
        )
        client.request(
            "POST",
            f"/reviews/{case_id}/approve",
            name="reviews.approve.non_agent_case",
            json_body={"actor": "load-test", "comment": "Close non-agent load-test case."},
            expected={200},
        )

    def exercise_employee_transaction_apis(
        self, client: ApiClient, iteration: int
    ) -> tuple[str | None, dict[str, Any] | None]:
        if not self.employee_id:
            return None, {
                "iteration": iteration,
                "status": None,
                "reason": "No authenticated employee/user id was resolved.",
            }
        payload = {
            "transaction_type": "reimbursement",
            "amount": 75.0 + iteration,
            "currency": "USD",
            "status": "pending",
            "description": "Load-test employee reimbursement.",
            "reference_id": f"LT-EMP-{self.run_id}-{iteration}",
        }
        status, body, result = client.request(
            "POST",
            "/employee-transactions",
            name="employee_transactions.create",
            json_body=payload,
            expected={201, 403, 404},
        )
        if status != 201 or not isinstance(body, dict):
            return None, {
                "iteration": iteration,
                "status": status,
                "reason": response_reason(body, result.error),
            }
        tx_id = str(body.get("id") or "")
        if not tx_id:
            return None, {
                "iteration": iteration,
                "status": status,
                "reason": "Create returned 201 but no transaction id.",
            }
        employee_id = str(body.get("employee_id") or self.employee_id)
        client.request("GET", "/employee-transactions", name="employee_transactions.list")
        client.request(
            "GET",
            f"/employee-transactions/employee/{employee_id}",
            name="employee_transactions.by_employee",
        )
        client.request(
            "GET",
            f"/employee-transactions/{tx_id}",
            name="employee_transactions.get",
        )
        client.request(
            "PUT",
            f"/employee-transactions/{tx_id}",
            name="employee_transactions.update",
            json_body={"status": "completed", "amount": 80.0 + iteration},
        )
        client.request(
            "DELETE",
            f"/employee-transactions/{tx_id}",
            name="employee_transactions.archive",
        )
        return tx_id, None

    def exercise_analytics_apis(self, client: ApiClient) -> None:
        for name, path, query in [
            ("analytics.trend", "/analytics/trend", None),
            ("analytics.agent_accuracy", "/analytics/agent-accuracy", None),
            ("analytics.kpis", "/analytics/kpis", None),
            ("analytics.requests", "/analytics/requests", {"limit": 200}),
            ("analytics.llm.summary", "/analytics/llm/summary", None),
            ("analytics.llm.by_provider", "/analytics/llm/by-provider", None),
            ("analytics.llm.by_model", "/analytics/llm/by-model", None),
            ("analytics.llm.recent_calls", "/analytics/llm/recent-calls", {"limit": 20}),
            ("analytics.llm.cost_trends", "/analytics/llm/cost-trends", None),
        ]:
            client.request("GET", path, name=name, query=query)

    def fetch_prometheus_metrics(self) -> dict[str, float]:
        status, payload, _ = self.client.request(
            "GET",
            "/metrics",
            name="prometheus.metrics",
            root=True,
            expected={200},
            auth=False,
        )
        if status != 200 or not isinstance(payload, str):
            return {}
        return parse_prometheus(payload)

    def build_report(
        self,
        scenario_results: list[ScenarioResult],
        elapsed_seconds: float,
    ) -> dict[str, Any]:
        all_results = list(self.client.results)
        durations = [result.duration_ms for result in all_results]
        status_counts = Counter(str(result.status) for result in all_results)
        endpoint_counts = Counter(result.name for result in all_results)
        failures = [dataclasses.asdict(result) for result in all_results if not result.ok]
        created_case_ids = [
            case_id for result in scenario_results for case_id in result.created_case_ids
        ]
        executed_case_ids = [
            case_id for result in scenario_results for case_id in result.executed_case_ids
        ]
        terminal_case_ids = [
            case_id for result in scenario_results for case_id in result.terminal_case_ids
        ]
        employee_transaction_ids = [
            tx_id for result in scenario_results for tx_id in result.employee_transaction_ids
        ]
        employee_transaction_skips = [
            skip for result in scenario_results for skip in result.employee_transaction_skips
        ]
        case_observability = {
            case_id: observation
            for result in scenario_results
            for case_id, observation in result.case_observability.items()
        }
        return {
            "run_id": self.run_id,
            "base_url": self.args.base_url,
            "config": {
                "users": self.args.users,
                "iterations": self.args.iterations,
                "agent_cases": self.args.agent_cases,
                "skip_agent_execution": self.args.skip_agent_execution,
                "allow_missing_agent_prometheus": self.args.allow_missing_agent_prometheus,
                "poll_timeout": self.args.poll_timeout,
                "max_error_rate": self.args.max_error_rate,
            },
            "elapsed_seconds": round(elapsed_seconds, 3),
            "totals": {
                "requests": len(all_results),
                "failures": len(failures),
                "error_rate": round(len(failures) / len(all_results), 4)
                if all_results
                else 0.0,
                "created_cases": len(created_case_ids),
                "executed_cases": len(executed_case_ids),
                "terminal_cases": len(terminal_case_ids),
                "employee_transactions": len(employee_transaction_ids),
            },
            "latency_ms": {
                "min": round(min(durations), 2) if durations else 0.0,
                "mean": round(statistics.mean(durations), 2) if durations else 0.0,
                "p50": percentile(durations, 0.50),
                "p95": percentile(durations, 0.95),
                "p99": percentile(durations, 0.99),
                "max": round(max(durations), 2) if durations else 0.0,
            },
            "status_counts": dict(sorted(status_counts.items())),
            "endpoint_counts": dict(sorted(endpoint_counts.items())),
            "created_case_ids": created_case_ids,
            "executed_case_ids": executed_case_ids,
            "terminal_case_ids": terminal_case_ids,
            "employee_transaction_ids": employee_transaction_ids,
            "employee_transaction_skips": employee_transaction_skips,
            "case_observability": case_observability,
            "metrics_delta": metric_delta(self.metrics_before, self.metrics_after),
            "analytics_before": self.analytics_before,
            "analytics_after": self.analytics_after,
            "failures": failures[:100],
        }

    def validate(self, report: dict[str, Any]) -> None:
        totals = report["totals"]
        error_rate = float(totals["error_rate"])
        if error_rate > self.args.max_error_rate:
            self.validation_failures.append(
                f"HTTP/API error rate {error_rate:.4f} exceeded threshold "
                f"{self.args.max_error_rate:.4f}"
            )

        if not self.metrics_after:
            self.validation_failures.append("Prometheus /metrics was unavailable or unparsable")
        else:
            self.validate_prometheus_metrics(report)

        self.validate_request_analytics()
        self.validate_llm_analytics()
        self.validate_employee_transaction_coverage(report)
        self.validate_domain_shapes()
        report["validation"] = {
            "passed": not self.validation_failures,
            "failures": self.validation_failures,
            "warnings": self.validation_warnings,
        }

    def validate_prometheus_metrics(self, report: dict[str, Any]) -> None:
        metric_names = set(self.metrics_after)
        if not any(name.startswith("http_") for name in metric_names):
            self.validation_failures.append("Prometheus output did not include HTTP metrics")

        executed = int(report["totals"]["terminal_cases"])
        delta = report["metrics_delta"]
        if executed:
            expected_agent_metrics = (
                ("skeptic_investigations_total", "terminal investigations"),
                ("skeptic_debate_rounds_total", "agent debate rounds"),
                ("skeptic_verification_results_total", "verification results"),
            )
            missing = []
            for metric_name, label in expected_agent_metrics:
                actual = float(delta.get(metric_name, 0.0))
                if actual < executed:
                    missing.append(
                        f"{metric_name} delta={actual}, expected>={executed} ({label})"
                    )
            if missing:
                observed = self.observed_terminal_agent_cases(report)
                message = (
                    "Agent Prometheus counters did not increase enough: "
                    + "; ".join(missing)
                )
                if observed:
                    message += (
                        f". API/DB artifacts were observed for {len(observed)}/"
                        f"{executed} terminal agent case(s), so this points to "
                        "Celery worker or Uvicorn multiprocess metrics not being "
                        "exported/merged into /metrics."
                    )
                else:
                    message += (
                        ". No terminal case artifacts were observed through the API; "
                        "verify both agent execution and metrics export."
                    )
                if self.args.allow_missing_agent_prometheus and observed:
                    self.validation_warnings.append(
                        message + " Allowed by --allow-missing-agent-prometheus."
                    )
                else:
                    self.validation_failures.append(message)

        for metric_name, value in self.metrics_after.items():
            if value < 0:
                self.validation_failures.append(f"Prometheus metric {metric_name} is negative")

    def observed_terminal_agent_cases(self, report: dict[str, Any]) -> list[str]:
        observations = report.get("case_observability")
        if not isinstance(observations, dict):
            return []

        observed: list[str] = []
        for case_id in report.get("terminal_case_ids", []):
            observation = observations.get(case_id)
            if not isinstance(observation, dict):
                continue
            artifact_count = sum(
                int(observation.get(key) or 0)
                for key in ("evidence_count", "debate_count", "verification_count")
            )
            workflow_done = int(observation.get("workflow_done_steps") or 0)
            if artifact_count > 0 or workflow_done > 1:
                observed.append(str(case_id))
        return observed

    def validate_request_analytics(self) -> None:
        after = self.analytics_after.get("requests")
        if not isinstance(after, dict):
            self.validation_failures.append("/analytics/requests did not return an object")
            return
        required = {"total_requests", "error_rate", "avg_duration_ms", "p95_duration_ms"}
        missing = sorted(required - set(after))
        if missing:
            self.validation_failures.append(
                f"/analytics/requests missing fields: {', '.join(missing)}"
            )
        if float(after.get("error_rate") or 0.0) > self.args.max_error_rate:
            self.validation_failures.append(
                "/analytics/requests error_rate exceeded threshold: "
                f"{after.get('error_rate')}"
            )
        if float(after.get("avg_duration_ms") or 0.0) < 0:
            self.validation_failures.append("/analytics/requests avg_duration_ms is negative")

    def validate_llm_analytics(self) -> None:
        summary = self.analytics_after.get("llm_summary")
        if not isinstance(summary, dict):
            self.validation_failures.append("/analytics/llm/summary did not return an object")
            return
        prompt = int(summary.get("prompt_tokens") or 0)
        completion = int(summary.get("completion_tokens") or 0)
        total = int(summary.get("total_tokens") or 0)
        if total and total != prompt + completion:
            self.validation_failures.append(
                "LLM token accounting is inconsistent: "
                f"total={total}, prompt+completion={prompt + completion}"
            )
        for field in (
            "total_estimated_cost_usd",
            "successful_calls",
            "failed_calls",
            "fallback_calls",
            "cache_hits",
            "average_latency_ms",
        ):
            if float(summary.get(field) or 0.0) < 0:
                self.validation_failures.append(f"LLM summary field {field} is negative")

        for group_name in ("llm_by_provider", "llm_by_model"):
            rows = self.analytics_after.get(group_name)
            if not isinstance(rows, list):
                self.validation_failures.append(f"/analytics/{group_name} did not return a list")
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                calls = int(row.get("calls") or 0)
                successful = int(row.get("successful_calls") or 0)
                failed = int(row.get("failed_calls") or 0)
                if calls != successful + failed:
                    self.validation_failures.append(
                        f"{group_name} has calls != successful+failed: {row}"
                    )

        recent = self.analytics_after.get("llm_recent_calls")
        if isinstance(recent, list):
            for row in recent[:50]:
                if not isinstance(row, dict):
                    continue
                total_tokens = int(row.get("total_tokens") or 0)
                prompt_tokens = int(row.get("prompt_tokens") or 0)
                completion_tokens = int(row.get("completion_tokens") or 0)
                if total_tokens != prompt_tokens + completion_tokens:
                    self.validation_failures.append(
                        f"Recent LLM call token mismatch: {row.get('id')}"
                    )

    def validate_employee_transaction_coverage(self, report: dict[str, Any]) -> None:
        attempts = int(report.get("endpoint_counts", {}).get("employee_transactions.create", 0))
        created = int(report.get("totals", {}).get("employee_transactions", 0))
        if attempts <= 0 or created > 0:
            return

        skips = report.get("employee_transaction_skips")
        reason_counts: Counter[str] = Counter()
        if isinstance(skips, list):
            for skip in skips:
                if not isinstance(skip, dict):
                    continue
                status = skip.get("status")
                reason = str(skip.get("reason") or "No response detail")
                reason_counts[f"{status}: {reason}"] += 1
        reasons = "; ".join(
            f"{count}x {reason}" for reason, count in reason_counts.most_common(3)
        )
        self.validation_warnings.append(
            "Employee transaction CRUD was not completed because create did "
            f"not return 201 in {attempts} attempt(s)."
            + (f" Reasons: {reasons}." if reasons else "")
        )

    def validate_domain_shapes(self) -> None:
        required_endpoints = {
            "health.root",
            "health.detailed",
            "investigations.create",
            "claims.verify_preview",
            "claims.verify_evidence",
            "agents.health",
            "agents.workflow",
            "analytics.requests",
            "evaluation.summary",
            "settings.get",
            "knowledge.search",
        }
        called = {result.name for result in self.client.results}
        missing = sorted(required_endpoints - called)
        if missing:
            self.validation_failures.append(
                f"Load test did not exercise expected endpoints: {', '.join(missing)}"
            )

    def write_report(self, report: dict[str, Any]) -> None:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        path = REPORTS_DIR / f"comprehensive-api-agents-{self.run_id}.json"
        report["report_path"] = str(path)
        path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    def print_summary(self, report: dict[str, Any]) -> None:
        totals = report["totals"]
        latency = report["latency_ms"]
        print("\nSkeptic Engine comprehensive load test")
        print(f"  Report: {report['report_path']}")
        print(f"  Requests: {totals['requests']} ({totals['failures']} failures)")
        print(f"  Error rate: {totals['error_rate']:.4f}")
        print(
            "  Cases: "
            f"{totals['created_cases']} created, "
            f"{totals['executed_cases']} executed, "
            f"{totals['terminal_cases']} terminal"
        )
        print(
            "  Latency ms: "
            f"mean={latency['mean']}, p95={latency['p95']}, p99={latency['p99']}"
        )
        if self.validation_failures:
            print("  Validation: FAILED")
            for failure in self.validation_failures:
                print(f"    - {failure}")
        else:
            print("  Validation: PASSED")
        if self.validation_warnings:
            print("  Warnings:")
            for warning in self.validation_warnings:
                print(f"    - {warning}")


def parse_prometheus(text: str) -> dict[str, float]:
    values: dict[str, float] = defaultdict(float)
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.rsplit(None, 1)
        if len(parts) != 2:
            continue
        left, raw_value = parts
        name = left.split("{", 1)[0]
        try:
            values[name] += float(raw_value)
        except ValueError:
            continue
    return dict(values)


def response_reason(payload: Any, fallback: str | None = None) -> str:
    if fallback:
        return fallback
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if detail is not None:
            return str(detail)
        return json.dumps(payload, sort_keys=True)[:500]
    if isinstance(payload, str) and payload:
        return payload[:500]
    return "No response detail"


def metric_delta(before: dict[str, float], after: dict[str, float]) -> dict[str, float]:
    names = set(before) | set(after)
    return {
        name: round(float(after.get(name, 0.0)) - float(before.get(name, 0.0)), 6)
        for name in sorted(names)
    }


def percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * ratio)))
    return round(float(ordered[index]), 2)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load test all major Skeptic Engine APIs plus the agent workflow."
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("LOADTEST_BASE_URL", "http://localhost:8000/api/v1"),
        help="API root URL, usually http://localhost:8000/api/v1.",
    )
    parser.add_argument(
        "--users",
        type=int,
        default=int(os.getenv("LOADTEST_USERS", "4")),
        help="Concurrent worker threads.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=int(os.getenv("LOADTEST_ITERATIONS", "8")),
        help="Total scenario iterations.",
    )
    parser.add_argument(
        "--agent-cases",
        type=int,
        default=int(os.getenv("LOADTEST_AGENT_CASES", "2")),
        help="Number of created investigations to execute through the agent crew.",
    )
    parser.add_argument(
        "--skip-agent-execution",
        action="store_true",
        default=os.getenv("LOADTEST_SKIP_AGENT_EXECUTION", "").lower() in {"1", "true", "yes"},
        help="Exercise APIs without POST /investigations/{id}/execute.",
    )
    parser.add_argument(
        "--allow-missing-agent-prometheus",
        action="store_true",
        default=os.getenv("LOADTEST_ALLOW_MISSING_AGENT_PROMETHEUS", "").lower()
        in {"1", "true", "yes"},
        help=(
            "Do not fail when terminal agent cases have API/DB artifacts but "
            "process-local agent Prometheus counters do not increase."
        ),
    )
    parser.add_argument(
        "--poll-timeout",
        type=float,
        default=float(os.getenv("LOADTEST_POLL_TIMEOUT", "120")),
        help="Seconds to wait for each executed investigation to reach a terminal status.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=float(os.getenv("LOADTEST_POLL_INTERVAL", "2")),
        help="Seconds between investigation status polls.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("LOADTEST_REQUEST_TIMEOUT", "30")),
        help="Per-request timeout in seconds.",
    )
    parser.add_argument(
        "--max-error-rate",
        type=float,
        default=float(os.getenv("LOADTEST_MAX_ERROR_RATE", "0.02")),
        help="Fail validation when API error rate is above this ratio.",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("LOADTEST_API_TOKEN"),
        help="Bearer token for AUTH_REQUIRED=true environments.",
    )
    parser.add_argument(
        "--username",
        default=os.getenv("LOADTEST_API_USERNAME"),
        help="Username for /auth/token. A synthetic load-test user is registered when omitted.",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("LOADTEST_API_PASSWORD"),
        help="Password for /auth/token. A synthetic load-test user is registered when omitted.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.users < 1:
        raise SystemExit("--users must be >= 1")
    if args.iterations < 1:
        raise SystemExit("--iterations must be >= 1")
    if args.agent_cases < 0:
        raise SystemExit("--agent-cases must be >= 0")
    return LoadTest(args).run()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
