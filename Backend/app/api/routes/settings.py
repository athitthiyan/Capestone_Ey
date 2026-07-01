"""Runtime governance settings exposed to the UI."""

from fastapi import APIRouter, Depends

from app.core.config import settings as app_settings
from app.core.security import get_current_user
from app.schemas import AppSettingsOut

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=AppSettingsOut)
async def get_settings(user=Depends(get_current_user)):
    """Return non-secret runtime settings that drive UI policy controls."""
    del user
    return AppSettingsOut(
        reasoning_model=app_settings.CLAUDE_MODEL_REASONING,
        report_model=app_settings.CLAUDE_MODEL_LIGHTWEIGHT,
        auto_clear_threshold=app_settings.DEFAULT_CONFIDENCE_THRESHOLD,
        reviewer_threshold=app_settings.DEFAULT_ESCALATION_THRESHOLD,
        materiality=app_settings.DEFAULT_MATERIALITY_THRESHOLD,
        segregation_of_duties=app_settings.ENFORCE_SEGREGATION_OF_DUTIES,
        immutable_audit_log=app_settings.IMMUTABLE_AUDIT_LOG_REQUIRED,
        debate_round_cap=app_settings.MAX_DEBATE_ROUNDS,
        api_key_vault=app_settings.API_KEY_VAULT_NAME,
        theme=app_settings.UI_THEME,
        display_currency=app_settings.DISPLAY_CURRENCY,
        notifications=app_settings.NOTIFICATIONS_ENABLED,
        audit_retention_years=app_settings.AUDIT_RETENTION_YEARS,
        ip_allowlist=app_settings.IP_ALLOWLIST_ENABLED,
        estimated_agent_run_cost_usd=app_settings.ESTIMATED_AGENT_RUN_COST_USD,
    )
