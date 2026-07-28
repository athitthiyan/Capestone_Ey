"""Live LLM access for the experiment harness.

Design constraints that follow from the evaluation protocol:

* **No hidden fixtures.** If a call cannot be made, the runner records an error row. It
  never substitutes a canned answer for a live measurement.
* **Deterministic replay.** Every request/response pair is content-addressed and cached
  on disk, so re-running the analysis costs nothing and reproduces byte-identical model
  output. ``--no-cache`` forces fresh calls.
* **Measured, not estimated, usage.** Token counts come from the provider response.
  Cost is those counts multiplied by an explicit, versioned price table; an unknown
  model fails loudly rather than silently costing ``0.0``.
* **Zero third-party dependencies.** ``urllib`` only, so the harness runs in any
  checkout without an SDK version pinned to it.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "experiments" / "runs" / "cache"

PRICE_TABLE_VERSION = "2026-07-28"

#: USD per 1,000,000 tokens, (input, output). Verified against published rate cards on
#: PRICE_TABLE_VERSION. Models absent here must be priced explicitly via
#: ``LLMConfig(price_per_mtok_in=..., price_per_mtok_out=...)`` so no run reports a
#: fabricated cost.
PRICE_TABLE: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    "claude-sonnet-4-5-20250929": (3.00, 15.00),
    "claude-opus-4-1-20250805": (15.00, 75.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1-mini": (0.40, 1.60),
}

RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504, 529}


class ProviderError(RuntimeError):
    """Raised when a provider call cannot be completed after the configured retries."""


@dataclass(frozen=True)
class Completion:
    text: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: float
    model: str
    provider: str
    cached: bool = False
    attempts: int = 1


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model: str
    temperature: float = 0.0
    max_tokens: int = 1024
    timeout_seconds: int = 90
    retries: int = 3
    use_cache: bool = True
    price_per_mtok_in: float | None = None
    price_per_mtok_out: float | None = None
    api_key_env: str = ""

    def prices(self) -> tuple[float, float]:
        if self.price_per_mtok_in is not None and self.price_per_mtok_out is not None:
            return self.price_per_mtok_in, self.price_per_mtok_out
        if self.model not in PRICE_TABLE:
            raise ProviderError(
                f"no price entry for model {self.model!r} in price table "
                f"{PRICE_TABLE_VERSION}; pass explicit prices so reported cost is not invented"
            )
        return PRICE_TABLE[self.model]

    def resolved_key_env(self) -> str:
        if self.api_key_env:
            return self.api_key_env
        return {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}.get(
            self.provider, "")


def _cost(input_tokens: int, output_tokens: int, prices: tuple[float, float]) -> float:
    return round(input_tokens / 1e6 * prices[0] + output_tokens / 1e6 * prices[1], 8)


def _cache_key(config: LLMConfig, system: str, user: str) -> str:
    payload = json.dumps({
        "provider": config.provider, "model": config.model,
        "temperature": config.temperature, "max_tokens": config.max_tokens,
        "system": system, "user": user,
    }, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ResponseCache:
    """Content-addressed on-disk cache. One JSON file per request hash."""

    def __init__(self, directory: Path = CACHE_DIR) -> None:
        self.directory = directory
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> dict | None:
        path = self.directory / f"{key}.json"
        if not path.exists():
            self.misses += 1
            return None
        self.hits += 1
        return json.loads(path.read_text(encoding="utf-8"))

    def put(self, key: str, payload: dict) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / f"{key}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _post_json(url: str, headers: dict[str, str], body: dict, timeout: int) -> dict:
    request = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"content-type": "application/json", **headers}, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class Provider:
    name = "base"

    def __init__(self, config: LLMConfig, cache: ResponseCache | None = None) -> None:
        self.config = config
        self.cache = cache if cache is not None else ResponseCache()

    # -- provider specific -------------------------------------------------
    def _request(self, api_key: str, system: str, user: str) -> dict:
        raise NotImplementedError

    def _parse(self, payload: dict) -> tuple[str, int, int]:
        raise NotImplementedError

    # -- shared ------------------------------------------------------------
    def api_key(self) -> str:
        env = self.config.resolved_key_env()
        key = os.environ.get(env, "").strip()
        if not key:
            raise ProviderError(
                f"{env} is not set. The harness refuses to emit results without a live call."
            )
        return key

    def complete(self, system: str, user: str) -> Completion:
        key = _cache_key(self.config, system, user)
        if self.config.use_cache:
            cached = self.cache.get(key)
            if cached is not None:
                return Completion(
                    text=cached["text"], input_tokens=cached["input_tokens"],
                    output_tokens=cached["output_tokens"],
                    cost_usd=_cost(cached["input_tokens"], cached["output_tokens"],
                                   self.config.prices()),
                    latency_ms=cached["latency_ms"], model=self.config.model,
                    provider=self.config.provider, cached=True,
                    attempts=cached.get("attempts", 1))

        api_key = self.api_key()
        last_error: Exception | None = None
        for attempt in range(1, self.config.retries + 1):
            started = time.perf_counter()
            try:
                payload = self._request(api_key, system, user)
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code not in RETRYABLE_STATUS or attempt == self.config.retries:
                    detail = exc.read().decode("utf-8", "replace")[:400]
                    raise ProviderError(
                        f"{self.config.provider} HTTP {exc.code}: {detail}") from exc
                time.sleep(min(30.0, 1.5 * 2 ** (attempt - 1)))
                continue
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt == self.config.retries:
                    raise ProviderError(
                        f"{self.config.provider} transport failure: {exc}") from exc
                time.sleep(min(30.0, 1.5 * 2 ** (attempt - 1)))
                continue

            latency_ms = (time.perf_counter() - started) * 1000
            text, input_tokens, output_tokens = self._parse(payload)
            if self.config.use_cache:
                self.cache.put(key, {
                    "text": text, "input_tokens": input_tokens,
                    "output_tokens": output_tokens, "latency_ms": latency_ms,
                    "attempts": attempt, "provider": self.config.provider,
                    "model": self.config.model,
                })
            return Completion(text=text, input_tokens=input_tokens,
                              output_tokens=output_tokens,
                              cost_usd=_cost(input_tokens, output_tokens,
                                             self.config.prices()),
                              latency_ms=latency_ms, model=self.config.model,
                              provider=self.config.provider, attempts=attempt)
        raise ProviderError(f"{self.config.provider} exhausted retries: {last_error}")


class AnthropicProvider(Provider):
    name = "anthropic"
    endpoint = "https://api.anthropic.com/v1/messages"

    def _request(self, api_key: str, system: str, user: str) -> dict:
        return _post_json(self.endpoint, {
            "x-api-key": api_key, "anthropic-version": "2023-06-01",
        }, {
            "model": self.config.model, "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature, "system": system,
            "messages": [{"role": "user", "content": user}],
        }, self.config.timeout_seconds)

    def _parse(self, payload: dict) -> tuple[str, int, int]:
        blocks = payload.get("content") or []
        text = "".join(block.get("text", "") for block in blocks if block.get("type") == "text")
        usage = payload.get("usage") or {}
        return text, int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))


class OpenAIProvider(Provider):
    name = "openai"
    endpoint = "https://api.openai.com/v1/chat/completions"

    def _request(self, api_key: str, system: str, user: str) -> dict:
        return _post_json(self.endpoint, {
            "authorization": f"Bearer {api_key}",
        }, {
            "model": self.config.model, "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
        }, self.config.timeout_seconds)

    def _parse(self, payload: dict) -> tuple[str, int, int]:
        choices = payload.get("choices") or [{}]
        text = (choices[0].get("message") or {}).get("content") or ""
        usage = payload.get("usage") or {}
        return text, int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0))


PROVIDERS = {"anthropic": AnthropicProvider, "openai": OpenAIProvider}


def build_provider(config: LLMConfig, cache: ResponseCache | None = None) -> Provider:
    if config.provider not in PROVIDERS:
        raise ProviderError(
            f"unknown provider {config.provider!r}; available: {sorted(PROVIDERS)}")
    return PROVIDERS[config.provider](config, cache)


# ---------------------------------------------------------------------------
# Structured-output parsing
# ---------------------------------------------------------------------------

@dataclass
class ParsedVerdict:
    prediction: int
    confidence: float
    explanation: str
    citations: list[str] = field(default_factory=list)
    raw: str = ""


def parse_verdict(text: str, *, allowed_citations: set[str] | None = None) -> ParsedVerdict:
    """Extract the JSON verdict from a model response.

    Models occasionally wrap JSON in prose or a fenced block, so the first balanced
    top-level object is located rather than assuming the whole response is JSON. A
    response that cannot be parsed raises, and the caller records it as a parse failure
    instead of guessing a prediction.
    """
    candidate = _first_json_object(text)
    if candidate is None:
        raise ValueError("no JSON object found in response")
    data = json.loads(candidate)

    if "prediction" not in data:
        raise ValueError("response is missing 'prediction'")
    prediction = data["prediction"]
    if isinstance(prediction, str):
        lowered = prediction.strip().lower()
        if lowered not in {"0", "1", "risk", "no_risk", "true", "false"}:
            raise ValueError(f"unparseable prediction {prediction!r}")
        prediction = 1 if lowered in {"1", "risk", "true"} else 0
    prediction = int(prediction)
    if prediction not in (0, 1):
        raise ValueError("prediction must be 0 or 1")

    confidence = float(data.get("confidence", 0.5))
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be in [0, 1]")

    citations = data.get("citations") or []
    if not isinstance(citations, list):
        raise ValueError("citations must be a list")
    citations = [str(item) for item in citations]
    if allowed_citations is not None:
        citations = [item for item in citations if item in allowed_citations]

    return ParsedVerdict(prediction=prediction, confidence=confidence,
                         explanation=str(data.get("explanation", "")).strip(),
                         citations=citations, raw=text)


def _first_json_object(text: str) -> str | None:
    depth = 0
    start = -1
    in_string = False
    escaped = False
    for index, character in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character == "{":
            if depth == 0:
                start = index
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                return text[start:index + 1]
    return None
