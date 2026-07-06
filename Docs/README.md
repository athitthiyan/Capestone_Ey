# Skeptic Engine - Documentation

Enterprise documentation set for the Skeptic Engine multi-agent AI audit-investigation
platform. Every document here was written by verifying the running source code as the
single source of truth (Backend `app/` package, `UI/`, infra manifests, and CI/CD),
not by trusting prior prose.

**Product version:** `0.1.0` (`Backend/app/core/config.py` -> `APP_VERSION`)
**Last full audit:** 2026-07-06

## Reading order by role

| Role | Start here |
|------|-----------|
| New engineer | [Local Development](LOCAL_DEVELOPMENT.md) -> [Architecture](ARCHITECTURE.md) -> [API Reference](API_REFERENCE.md) |
| DevOps / SRE | [Deployment](DEPLOYMENT.md) -> [Infrastructure](INFRASTRUCTURE.md) -> [Runbook](RUNBOOK.md) |
| On-call | [Runbook](RUNBOOK.md) -> [Incident Response](INCIDENT_RESPONSE.md) -> [Troubleshooting](TROUBLESHOOTING.md) |
| Security / Auditor | [Security](SECURITY.md) -> [Architecture](ARCHITECTURE.md) -> [Audit Report](AUDIT_REPORT.md) |
| QA | [CI/CD](CICD.md) -> [Troubleshooting](TROUBLESHOOTING.md) |
| Business stakeholder | [Architecture](ARCHITECTURE.md) (overview section) |

## Index

### Audit and planning
- [Documentation Audit Report and Gap Analysis](AUDIT_REPORT.md)
- [Known Issues and Workarounds](KNOWN_ISSUES.md)
- [Engineering Challenges and Lessons Learned](LESSONS_LEARNED.md)
- [Final Validation Report and Improvement Recommendations](VALIDATION_REPORT.md)

### Architecture and reference
- [Architecture and Data Flow](ARCHITECTURE.md)
- [API Reference](API_REFERENCE.md)
- [Environment Variable Reference](ENVIRONMENT_VARIABLES.md)
- [Security and Secrets](SECURITY.md)

### Deployment and infrastructure
- [Local Development Guide](LOCAL_DEVELOPMENT.md)
- [Deployment Guide (Docker, Compose, Railway, Kubernetes, Cloud)](DEPLOYMENT.md)
- [CI/CD Guide](CICD.md)
- [Infrastructure Guide](INFRASTRUCTURE.md)

### Operations
- [Operations Runbook](RUNBOOK.md)
- [Monitoring and Logging](MONITORING_LOGGING.md)
- [Incident Response](INCIDENT_RESPONSE.md)
- [Troubleshooting](TROUBLESHOOTING.md)
- [Backup and Restore](BACKUP_RESTORE.md)
- [Disaster Recovery](DISASTER_RECOVERY.md)
- [Maintenance](MAINTENANCE.md)

## Source-of-truth map

| Topic | Authoritative file(s) |
|-------|----------------------|
| Configuration / env vars | `Backend/app/core/config.py` |
| App wiring, middleware, routers | `Backend/app/main.py` |
| HTTP/WS routes | `Backend/app/api/routes/*.py` |
| Data model | `Backend/app/db/models.py`, `Backend/migrations/versions/` |
| Agent pipeline | `Backend/app/agents/executor.py`, `crew.py` |
| LLM routing | `Backend/app/llm/` |
| Background jobs | `Backend/app/tasks/celery_app.py` |
| Local infra | `Backend/docker-compose.yml` |
| Production infra | `docker-compose.production.yml`, `Backend/k8s-deployment.yaml`, `Backend/railway.*.json` |
| CI/CD | `.github/workflows/ci-cd.yml` |
| Frontend | `UI/` (Next.js 15, React 19) |
