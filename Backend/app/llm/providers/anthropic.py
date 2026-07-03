"""Anthropic Messages API client."""

from __future__ import annotations

from typing import Any

import requests

from app.core.config import settings
from app.llm.providers.base import request_exception, response_error
from app.llm.types import LLMRequest, ProviderResponse

# Verdict agents must return strict JSON. Anthropic has no OpenAI-style
# response_format=json_object mode, so instead we prefill the assistant turn
# with "{" - a documented Anthropic technique that biases the completion to
# continue a JSON object instead of wrapping it in prose or markdown fences.
JSON_REQUEST_TYPES = {"adjudication", "verification"}
_JSON_PREFILL = "{"


class AnthropicProvider:
    name = "anthropic"
    endpoint = "https://api.anthropic.com/v1/messages"

    def complete(
        self,
        request: LLMRequest,
        *,
        model: str,
        api_key: str,
        timeout_seconds: float,
    ) -> ProviderResponse:
        messages: list[dict[str, Any]] = [{"role": "user", "content": request.prompt}]
        wants_json = request.request_type.lower() in JSON_REQUEST_TYPES
        if wants_json:
            messages.append({"role": "assistant", "content": _JSON_PREFILL})

        body: dict[str, Any] = {
            "model": model,
            "max_tokens": request.max_tokens or 4000,
            "temperature": settings.ANTHROPIC_TEMPERATURE if request.temperature is None else request.temperature,
            "messages": messages,
        }
        if request.system_prompt:
            # The role/guardrail instructions are identical across every call
            # of a given request_type - marking them cacheable lets Anthropic
            # skip re-billing (and re-processing) those input tokens on every
            # investigation instead of just this process's short-lived,
            # per-prompt LLMResponseCache (which can't hit across different
            # transactions since the user prompt is unique each time).
            body["system"] = [
                {
                    "type": "text",
                    "text": request.system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ]

        try:
            response = requests.post(
                self.endpoint,
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "anthropic-beta": "prompt-caching-2024-07-31",
                    "content-type": "application/json",
                },
                json=body,
                timeout=timeout_seconds,
            )
        except requests.RequestException as exc:
            raise request_exception(self.name, exc) from exc

        if not response.ok:
            raise response_error(self.name, response)

        payload = response.json()
        content = "".join(
            item.get("text", "")
            for item in payload.get("content", [])
            if isinstance(item, dict) and item.get("type") == "text"
        )
        if wants_json and content and not content.lstrip().startswith("{"):
            # The API only returns the continuation, not the prefill itself -
            # stitch it back on so _extract_json sees a complete object.
            content = _JSON_PREFILL + content
        usage = payload.get("usage") or {}
        return ProviderResponse(
            content=content,
            model=str(payload.get("model") or model),
            prompt_tokens=usage.get("input_tokens"),
            completion_tokens=usage.get("output_tokens"),
            raw=payload,
        )
