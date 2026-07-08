"""Concrete free-tier / keyless provider adapters for evidence verification.

These complement the generic ``ConfiguredHttpBenchmarkProvider`` (which POSTs a
claim to a configured wrapper URL). The adapters here talk to specific real APIs.

Currently implemented:
- ``FrankfurterFxProvider``: keyless currency conversion via https://frankfurter.app.
  Used for the "fx"/"currency" category to convert a claimed amount into a target
  currency. No API key required, so it works out of the box.
- ``IndianApiFuelProvider``: live per-litre fuel price via https://fuel.indianapi.in
  (``x-api-key`` header). Used for the "fuel" category when an API key is set.

The GST, flight, hotel, food, and cab categories continue to use the generic
configured-URL provider; add a free-tier provider URL + key in the environment to
enable them.
"""

from __future__ import annotations

import re
import statistics
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import requests

from app.core.config import settings

if TYPE_CHECKING:  # pragma: no cover - hints only, avoids a runtime import cycle
    from app.evidence_verification.service import (
        ClaimEvidenceInput,
        ProviderBenchmarkResult,
    )


class FrankfurterFxProvider:
    """Keyless FX conversion using the Frankfurter API (ECB reference rates)."""

    provider_name = "frankfurter_fx"

    def fetch_benchmark(self, claim: "ClaimEvidenceInput") -> "ProviderBenchmarkResult":
        # Imported here to avoid a circular import at module load time.
        from app.evidence_verification.service import (
            STATUS_NEEDS_MANUAL_REVIEW,
            STATUS_VERIFIED,
            ProviderBenchmarkResult,
            ProviderUnavailableError,
        )

        base = (claim.currency or "INR").upper()
        target = str(
            claim.metadata.get("target_currency")
            or settings.DISPLAY_CURRENCY
            or "USD"
        ).upper()

        if claim.claimed_amount <= 0:
            return ProviderBenchmarkResult(
                provider_name=self.provider_name,
                reference_amount=None,
                provider_reference_id=None,
                confidence=0.4,
                reason="A positive claimed amount is required to convert currency.",
                raw_response={"base": base, "target": target},
                status_override=STATUS_NEEDS_MANUAL_REVIEW,
            )

        if base == target:
            return ProviderBenchmarkResult(
                provider_name=self.provider_name,
                reference_amount=round(claim.claimed_amount, 2),
                provider_reference_id=f"{base}->{target}",
                confidence=1.0,
                reason=f"Claim is already in {target}; no conversion required.",
                raw_response={"base": base, "target": target, "rate": 1.0},
                status_override=STATUS_VERIFIED,
            )

        url = f"{settings.FX_API_BASE_URL.rstrip('/')}/latest"
        try:
            response = requests.get(
                url,
                params={"amount": claim.claimed_amount, "from": base, "to": target},
                timeout=settings.EVIDENCE_VERIFICATION_PROVIDER_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()
            converted = float(data["rates"][target])
        except Exception as exc:  # noqa: BLE001
            raise ProviderUnavailableError(
                f"Frankfurter FX lookup failed for {base}->{target}: {exc}"
            ) from exc

        implied_rate = converted / claim.claimed_amount if claim.claimed_amount else None
        return ProviderBenchmarkResult(
            provider_name=self.provider_name,
            reference_amount=round(converted, 2),
            provider_reference_id=f"{base}->{target}",
            confidence=0.97,
            reason=(
                f"Converted {claim.claimed_amount:,.2f} {base} to "
                f"{converted:,.2f} {target} at ECB reference rate"
                + (f" ({implied_rate:.4f})." if implied_rate else ".")
            ),
            raw_response=data,
            status_override=STATUS_VERIFIED,
        )


# Keys that commonly hold a per-litre retail price in fuel-API responses.
_FUEL_PRICE_KEYS = (
    "retailPrice",
    "retail_price",
    "price",
    "rate",
    "amount",
    "value",
    "todayPrice",
    "today_price",
)


def _to_float(value: Any) -> float | None:
    """Coerce numbers or price-like strings (e.g. "Rs 102.34/L") to float."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.search(r"[0-9]+(?:\.[0-9]+)?", value.replace(",", ""))
        if match:
            return float(match.group(0))
    return None


def _find_fuel_price(node: Any, fuel_type: str) -> float | None:
    """Recursively search a fuel-API JSON response for the per-litre price.

    The IndianAPI fuel schema is not published, so this walks the structure and
    handles the common shapes:
      * an object tagged by fuel type: {"type": "petrol", "price": 101.2}
      * a sub-object keyed by fuel type: {"petrol": {"retailPrice": 102.3}}
      * a numeric value directly under a fuel-type key: {"petrol": 102.3}
    """
    fuel_type = fuel_type.lower()

    if isinstance(node, dict):
        # Case A: an object tagged with its fuel type.
        type_value = node.get("type") or node.get("fuel") or node.get("name")
        if isinstance(type_value, str) and type_value.lower() == fuel_type:
            for price_key in _FUEL_PRICE_KEYS:
                price = _to_float(node.get(price_key))
                if price is not None and price > 0:
                    return price
        # Case B: a sub-object explicitly keyed by the requested fuel type.
        for key, child in node.items():
            if str(key).lower() == fuel_type:
                if isinstance(child, dict):
                    for price_key in _FUEL_PRICE_KEYS:
                        price = _to_float(child.get(price_key))
                        if price is not None and price > 0:
                            return price
                direct = _to_float(child)
                if direct is not None and direct > 0:
                    return direct
        # Otherwise recurse into children.
        for child in node.values():
            found = _find_fuel_price(child, fuel_type)
            if found is not None:
                return found
    elif isinstance(node, list):
        for child in node:
            found = _find_fuel_price(child, fuel_type)
            if found is not None:
                return found
    return None


def _infer_fuel_type(claim: "ClaimEvidenceInput") -> str | None:
    text = " ".join(
        str(part)
        for part in (claim.source_category, claim.metadata.get("description"))
        if part
    ).lower()
    if "diesel" in text:
        return "diesel"
    if "cng" in text:
        return "cng"
    if "petrol" in text or "gasoline" in text:
        return "petrol"
    return None


class IndianApiFuelProvider:
    """Live per-litre fuel price via IndianAPI (https://fuel.indianapi.in).

    Auth is an ``x-api-key`` header. The claim must carry litres (parsed into
    ``quantity``) and a city (``location`` or metadata ``city``). The benchmark
    is ``price_per_litre * quantity`` for the claim's fuel type.
    """

    provider_name = "indianapi_fuel"

    def fetch_benchmark(self, claim: "ClaimEvidenceInput") -> "ProviderBenchmarkResult":
        from app.evidence_verification.service import (
            STATUS_NEEDS_MANUAL_REVIEW,
            ProviderBenchmarkResult,
            ProviderUnavailableError,
        )

        base_url = (settings.FUEL_PRICE_PROVIDER_URL or "https://fuel.indianapi.in").rstrip("/")
        api_key = settings.FUEL_PRICE_PROVIDER_API_KEY
        if not api_key:
            raise ProviderUnavailableError(
                "FUEL_PRICE_PROVIDER_API_KEY is not configured for the IndianAPI fuel provider."
            )

        city = claim.location or claim.metadata.get("city") or claim.metadata.get("location")
        state = claim.metadata.get("state")
        if not city and not state:
            return ProviderBenchmarkResult(
                provider_name=self.provider_name,
                reference_amount=None,
                provider_reference_id=None,
                confidence=0.4,
                reason="A city or state is required to look up a live fuel price.",
                raw_response={"missing_fields": ["city"]},
                status_override=STATUS_NEEDS_MANUAL_REVIEW,
            )

        quantity = claim.quantity
        if quantity is None or quantity <= 0:
            return ProviderBenchmarkResult(
                provider_name=self.provider_name,
                reference_amount=None,
                provider_reference_id=None,
                confidence=0.4,
                reason="A positive fuel quantity (litres) is required to benchmark the claim.",
                raw_response={"missing_fields": ["quantity"]},
                status_override=STATUS_NEEDS_MANUAL_REVIEW,
            )

        fuel_type = str(
            claim.metadata.get("fuel_type")
            or _infer_fuel_type(claim)
            or settings.FUEL_PRICE_DEFAULT_TYPE
        ).lower()

        url = f"{base_url}{settings.FUEL_PRICE_LIVE_PATH}"
        params: dict[str, Any] = {}
        if city:
            params["city"] = city
        if state:
            params["state"] = state
        headers = {"Accept": "application/json", settings.FUEL_PRICE_PROVIDER_HEADER: api_key}

        try:
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=settings.EVIDENCE_VERIFICATION_PROVIDER_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:  # noqa: BLE001
            raise ProviderUnavailableError(
                f"IndianAPI fuel lookup failed for {city or state}: {exc}"
            ) from exc

        price_per_litre = _find_fuel_price(data, fuel_type)
        if price_per_litre is None:
            return ProviderBenchmarkResult(
                provider_name=self.provider_name,
                reference_amount=None,
                provider_reference_id=None,
                confidence=0.4,
                reason=(
                    f"Could not locate a {fuel_type} price for {city or state} in the "
                    "provider response."
                ),
                raw_response=data if isinstance(data, dict) else {"response": data},
                status_override=STATUS_NEEDS_MANUAL_REVIEW,
            )

        reference_amount = round(price_per_litre * quantity, 2)
        return ProviderBenchmarkResult(
            provider_name=self.provider_name,
            reference_amount=reference_amount,
            provider_reference_id=f"{fuel_type}@{city or state}",
            confidence=0.9,
            reason=(
                f"Live {fuel_type} rate {price_per_litre:,.2f}/L x {quantity:g} L = "
                f"{reference_amount:,.2f} INR for {city or state}."
            ),
            raw_response=data if isinstance(data, dict) else {"response": data},
        )


_IATA_PATTERN = re.compile(r"^[A-Z]{3}$")


def _resolve_iata(claim: "ClaimEvidenceInput", direction: str) -> str | None:
    """Resolve a departure/arrival IATA code for a flight claim.

    Aviationstack needs IATA airport codes (e.g. MAA, DEL), not free-text city
    names. We accept an explicit code from metadata, or use the route field when
    it already looks like a 3-letter code. City->airport resolution is skipped on
    purpose (multiple airports per city + free-tier call budget); callers should
    pass ``dep_iata``/``arr_iata`` in metadata for automated validation.
    """
    if direction == "from":
        meta_keys = ("dep_iata", "origin_iata", "from_iata", "departure_iata")
        route_value = claim.route_from
    else:
        meta_keys = ("arr_iata", "destination_iata", "to_iata", "arrival_iata")
        route_value = claim.route_to

    for key in meta_keys:
        value = claim.metadata.get(key)
        if isinstance(value, str) and _IATA_PATTERN.match(value.strip().upper()):
            return value.strip().upper()

    if isinstance(route_value, str):
        candidate = route_value.strip().upper()
        if _IATA_PATTERN.match(candidate):
            return candidate
    return None


class AviationstackFlightProvider:
    """Flight *existence* validator via Aviationstack (schedules, not fares).

    Confirms a route genuinely exists in airline schedules using the ``/routes``
    endpoint. It returns no benchmark amount (``reference_amount`` is None); the
    status is VERIFIED when the route is found, FLAGGED when it is not, and
    NEEDS_MANUAL_REVIEW when IATA codes are unavailable. Pricing is out of scope
    for Aviationstack and should come from a dedicated fares API.
    """

    provider_name = "aviationstack_flight"

    def fetch_benchmark(self, claim: "ClaimEvidenceInput") -> "ProviderBenchmarkResult":
        from app.evidence_verification.service import (
            STATUS_FLAGGED,
            STATUS_NEEDS_MANUAL_REVIEW,
            STATUS_VERIFIED,
            ProviderBenchmarkResult,
            ProviderUnavailableError,
        )

        api_key = settings.FLIGHT_VALIDATION_API_KEY
        if not api_key:
            raise ProviderUnavailableError(
                "FLIGHT_VALIDATION_API_KEY is not configured for the Aviationstack provider."
            )

        dep = _resolve_iata(claim, "from")
        arr = _resolve_iata(claim, "to")
        if not dep or not arr:
            missing = [name for name, val in (("dep_iata", dep), ("arr_iata", arr)) if not val]
            return ProviderBenchmarkResult(
                provider_name=self.provider_name,
                reference_amount=None,
                provider_reference_id=None,
                confidence=0.4,
                reason=(
                    "Automated route validation needs IATA airport codes. Provide "
                    f"{', '.join(missing)} in the claim metadata (e.g. MAA, DEL)."
                ),
                raw_response={"missing_fields": missing},
                status_override=STATUS_NEEDS_MANUAL_REVIEW,
            )

        base_url = (
            settings.FLIGHT_VALIDATION_PROVIDER_URL or "https://api.aviationstack.com/v1"
        ).rstrip("/")
        url = f"{base_url}{settings.FLIGHT_VALIDATION_ROUTES_PATH}"
        params: dict[str, Any] = {
            "access_key": api_key,
            "dep_iata": dep,
            "arr_iata": arr,
            "limit": 20,
        }
        # Narrow the match when the claim names a specific airline / flight number.
        airline = claim.metadata.get("airline_iata") or claim.metadata.get("airline")
        if isinstance(airline, str) and _IATA_PATTERN.match(airline.strip().upper()):
            params["airline_iata"] = airline.strip().upper()
        flight_number = claim.metadata.get("flight_number")
        if flight_number:
            params["flight_number"] = str(flight_number)

        try:
            response = requests.get(
                url,
                params=params,
                headers={"Accept": "application/json"},
                timeout=settings.EVIDENCE_VERIFICATION_PROVIDER_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:  # noqa: BLE001
            raise ProviderUnavailableError(
                f"Aviationstack route lookup failed for {dep}->{arr}: {exc}"
            ) from exc

        # Aviationstack signals problems (bad key, quota) via an "error" payload.
        if isinstance(data, dict) and data.get("error"):
            raise ProviderUnavailableError(
                f"Aviationstack error for {dep}->{arr}: {data['error']}"
            )

        results = data.get("data") if isinstance(data, dict) else None
        results = results or []

        if results:
            airlines = sorted(
                {
                    str((r.get("airline") or {}).get("name") or (r.get("airline") or {}).get("iata"))
                    for r in results
                    if isinstance(r, dict) and r.get("airline")
                }
            )
            airline_note = f" Airlines: {', '.join(a for a in airlines if a)}." if airlines else ""
            return ProviderBenchmarkResult(
                provider_name=self.provider_name,
                reference_amount=None,
                provider_reference_id=f"{dep}->{arr}",
                confidence=0.85,
                reason=(
                    f"Route {dep}->{arr} exists in airline schedules "
                    f"({len(results)} scheduled route(s)).{airline_note} "
                    "Note: existence confirmed; ticket price is not validated by this provider."
                ),
                raw_response=data,
                status_override=STATUS_VERIFIED,
            )

        return ProviderBenchmarkResult(
            provider_name=self.provider_name,
            reference_amount=None,
            provider_reference_id=f"{dep}->{arr}",
            confidence=0.7,
            reason=(
                f"No scheduled route {dep}->{arr} was found in airline schedules; "
                "the flight claim could not be substantiated and may be fabricated."
            ),
            raw_response=data if isinstance(data, dict) else {"response": data},
            status_override=STATUS_FLAGGED,
        )


# Common legal-suffix noise stripped before comparing vendor names.
_NAME_STOPWORDS = {
    "pvt", "private", "ltd", "limited", "llp", "inc", "co", "company",
    "corporation", "corp", "the", "and", "&", "enterprises", "enterprise",
    "industries", "services", "solutions", "india",
}


def _name_tokens(value: str | None) -> set[str]:
    if not value:
        return set()
    cleaned = re.sub(r"[^a-z0-9 ]", " ", value.lower())
    return {t for t in cleaned.split() if t and t not in _NAME_STOPWORDS}


class GstinCheckProvider:
    """GSTIN validity/identity check via GSTINCheck (sheet.gstincheck.co.in).

    Path-based key: ``GET /check/{api_key}/{gstin}``. This is an identity check,
    not a price benchmark, so ``reference_amount`` is always None. An Active
    registration yields VERIFIED; a cancelled/suspended/not-found GSTIN yields
    FLAGGED. A vendor-name mismatch against the registered name is surfaced as a
    note with reduced confidence (not auto-flagged, to avoid false positives from
    legal-suffix formatting differences).
    """

    provider_name = "gstincheck"

    def fetch_benchmark(self, claim: "ClaimEvidenceInput") -> "ProviderBenchmarkResult":
        from app.evidence_verification.service import (
            STATUS_FLAGGED,
            STATUS_NEEDS_MANUAL_REVIEW,
            STATUS_VERIFIED,
            ProviderBenchmarkResult,
            ProviderUnavailableError,
        )

        api_key = settings.GST_VERIFICATION_PROVIDER_API_KEY
        if not api_key:
            raise ProviderUnavailableError(
                "GST_VERIFICATION_PROVIDER_API_KEY is not configured for GSTINCheck."
            )
        gstin = (claim.gstin or "").strip().upper()
        if not gstin:
            return ProviderBenchmarkResult(
                provider_name=self.provider_name,
                reference_amount=None,
                provider_reference_id=None,
                confidence=0.4,
                reason="No GSTIN was supplied for verification.",
                raw_response={"missing_fields": ["gstin"]},
                status_override=STATUS_NEEDS_MANUAL_REVIEW,
            )

        base_url = (
            settings.GST_VERIFICATION_BASE_URL or "https://sheet.gstincheck.co.in"
        ).rstrip("/")
        path = settings.GST_VERIFICATION_CHECK_PATH.strip("/")
        url = f"{base_url}/{path}/{api_key}/{gstin}"

        try:
            response = requests.get(
                url,
                headers={"Accept": "application/json"},
                timeout=settings.EVIDENCE_VERIFICATION_PROVIDER_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:  # noqa: BLE001
            raise ProviderUnavailableError(
                f"GSTINCheck lookup failed for {gstin}: {exc}"
            ) from exc

        flag = data.get("flag") if isinstance(data, dict) else None
        details = (data.get("data") if isinstance(data, dict) else None) or {}
        message = str(data.get("message") or "") if isinstance(data, dict) else ""

        # flag is False when the GSTIN is invalid / not found on the portal.
        if flag is False or not details:
            return ProviderBenchmarkResult(
                provider_name=self.provider_name,
                reference_amount=None,
                provider_reference_id=gstin,
                confidence=0.9,
                reason=f"GSTIN {gstin} was not found or is invalid on the GST portal. {message}".strip(),
                raw_response=data if isinstance(data, dict) else {"response": data},
                status_override=STATUS_FLAGGED,
            )

        status_text = str(details.get("sts") or details.get("status") or "").strip()
        legal_name = str(details.get("lgnm") or "").strip()
        trade_name = str(details.get("tradeNam") or details.get("tradeName") or "").strip()
        names = ", ".join(n for n in (legal_name, trade_name) if n) or "n/a"

        if status_text.lower() != "active":
            return ProviderBenchmarkResult(
                provider_name=self.provider_name,
                reference_amount=None,
                provider_reference_id=gstin,
                confidence=0.9,
                reason=(
                    f"GSTIN {gstin} registration status is '{status_text or 'unknown'}' "
                    f"(registered name: {names}); not an active taxpayer."
                ),
                raw_response=data,
                status_override=STATUS_FLAGGED,
            )

        # Active registration. Optionally note a vendor-name mismatch.
        confidence = 0.95
        note = ""
        vendor_tokens = _name_tokens(claim.vendor)
        registered_tokens = _name_tokens(legal_name) | _name_tokens(trade_name)
        if vendor_tokens and registered_tokens and not (vendor_tokens & registered_tokens):
            confidence = 0.6
            note = (
                f" Note: claimed vendor '{claim.vendor}' does not match the registered "
                f"name ({names}) — review for a possible mismatch."
            )

        return ProviderBenchmarkResult(
            provider_name=self.provider_name,
            reference_amount=None,
            provider_reference_id=gstin,
            confidence=confidence,
            reason=(
                f"GSTIN {gstin} is Active on the GST portal (registered name: {names})." + note
            ),
            raw_response=data,
            status_override=STATUS_VERIFIED,
        )


# --- Shared helpers for the Duffel providers -------------------------------

def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _frankfurter_convert(
    amount: float, base: str, target: str, timeout: float
) -> tuple[float, float | None]:
    """Convert ``amount`` from ``base`` to ``target`` via Frankfurter (ECB rates).

    Returns (converted_amount, implied_rate). Raises on network/parse failure so
    callers can decide how to degrade.
    """
    base = (base or "").upper()
    target = (target or "").upper()
    if not base or not target or base == target:
        return amount, 1.0
    url = f"{settings.FX_API_BASE_URL.rstrip('/')}/latest"
    response = requests.get(
        url, params={"amount": amount, "from": base, "to": target}, timeout=timeout
    )
    response.raise_for_status()
    data = response.json()
    converted = float(data["rates"][target])
    return converted, (converted / amount if amount else None)


# Coordinates for major Indian cities so hotel claims that only name a city can
# still be benchmarked. Callers may override with metadata latitude/longitude.
_INDIA_CITY_COORDS: dict[str, tuple[float, float]] = {
    "mumbai": (19.0760, 72.8777),
    "delhi": (28.6139, 77.2090),
    "new delhi": (28.6139, 77.2090),
    "bangalore": (12.9716, 77.5946),
    "bengaluru": (12.9716, 77.5946),
    "chennai": (13.0827, 80.2707),
    "kolkata": (22.5726, 88.3639),
    "hyderabad": (17.3850, 78.4867),
    "pune": (18.5204, 73.8567),
    "ahmedabad": (23.0225, 72.5714),
    "jaipur": (26.9124, 75.7873),
    "goa": (15.2993, 74.1240),
    "kochi": (9.9312, 76.2673),
    "cochin": (9.9312, 76.2673),
    "gurgaon": (28.4595, 77.0266),
    "gurugram": (28.4595, 77.0266),
    "noida": (28.5355, 77.3910),
    "lucknow": (26.8467, 80.9462),
    "chandigarh": (30.7333, 76.7794),
    "coimbatore": (11.0168, 76.9558),
    "indore": (22.7196, 75.8577),
    "nagpur": (21.1458, 79.0882),
    "surat": (21.1702, 72.8311),
}


def _duffel_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.DUFFEL_API_KEY}",
        "Duffel-Version": settings.DUFFEL_API_VERSION,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _int_from_metadata(metadata: dict[str, Any], key: str, default: int) -> int:
    try:
        value = int(metadata.get(key))
        return value if value > 0 else default
    except (TypeError, ValueError):
        return default


class DuffelFlightProvider:
    """Real airfare benchmark via Duffel offer requests (POST /air/offer_requests).

    Median offer total for the route + date is FX-converted to the claim currency
    and used as the benchmark. Needs IATA origin/destination (metadata dep_iata/
    arr_iata or 3-letter route fields) and a departure date. Test keys return
    synthetic fares, which is noted on the result.
    """

    provider_name = "duffel_flight"

    def fetch_benchmark(self, claim: "ClaimEvidenceInput") -> "ProviderBenchmarkResult":
        from app.evidence_verification.service import (
            STATUS_NEEDS_MANUAL_REVIEW,
            ProviderBenchmarkResult,
            ProviderUnavailableError,
        )

        if not settings.DUFFEL_API_KEY:
            raise ProviderUnavailableError("DUFFEL_API_KEY is not configured.")

        origin = _resolve_iata(claim, "from")
        destination = _resolve_iata(claim, "to")
        departure_date = claim.service_date
        missing = []
        if not origin:
            missing.append("dep_iata")
        if not destination:
            missing.append("arr_iata")
        if not departure_date:
            missing.append("service_date")
        if missing:
            return ProviderBenchmarkResult(
                provider_name=self.provider_name,
                reference_amount=None,
                provider_reference_id=None,
                confidence=0.4,
                reason=(
                    "Flight fare lookup needs IATA codes and a departure date. Missing: "
                    f"{', '.join(missing)} (e.g. dep_iata=MAA, arr_iata=DEL)."
                ),
                raw_response={"missing_fields": missing},
                status_override=STATUS_NEEDS_MANUAL_REVIEW,
            )

        passenger_count = _int_from_metadata(claim.metadata, "passengers", 1)
        cabin = str(claim.metadata.get("cabin_class") or "economy").lower()
        payload = {
            "data": {
                "slices": [
                    {
                        "origin": origin,
                        "destination": destination,
                        "departure_date": departure_date,
                    }
                ],
                "passengers": [{"type": "adult"}] * passenger_count,
                "cabin_class": cabin,
            }
        }
        base_url = (settings.DUFFEL_API_BASE_URL or "https://api.duffel.com").rstrip("/")
        url = f"{base_url}/air/offer_requests"
        params = {"return_offers": "true", "supplier_timeout": settings.DUFFEL_SUPPLIER_TIMEOUT_MS}

        try:
            response = requests.post(
                url,
                params=params,
                json=payload,
                headers=_duffel_headers(),
                timeout=settings.DUFFEL_HTTP_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:  # noqa: BLE001
            raise ProviderUnavailableError(
                f"Duffel offer request failed for {origin}->{destination}: {exc}"
            ) from exc

        request_data = data.get("data") if isinstance(data, dict) else {}
        offers = (request_data or {}).get("offers") or []
        amounts = [
            float(o["total_amount"])
            for o in offers
            if isinstance(o, dict) and o.get("total_amount") is not None
        ]
        if not amounts:
            return ProviderBenchmarkResult(
                provider_name=self.provider_name,
                reference_amount=None,
                provider_reference_id=(request_data or {}).get("id"),
                confidence=0.4,
                reason=(
                    f"Duffel returned no offers for {origin}->{destination} on {departure_date}. "
                    "In test mode inventory is limited; use a live key or verify manually."
                ),
                raw_response=data,
                status_override=STATUS_NEEDS_MANUAL_REVIEW,
            )

        supplier_currency = str(offers[0].get("total_currency") or "GBP").upper()
        supplier_median = _median(amounts)

        try:
            converted, rate = _frankfurter_convert(
                supplier_median,
                supplier_currency,
                claim.currency,
                settings.EVIDENCE_VERIFICATION_PROVIDER_TIMEOUT_SECONDS,
            )
        except Exception:  # noqa: BLE001 - FX is best-effort
            if supplier_currency != claim.currency.upper():
                return ProviderBenchmarkResult(
                    provider_name=self.provider_name,
                    reference_amount=None,
                    provider_reference_id=(request_data or {}).get("id"),
                    confidence=0.4,
                    reason=(
                        f"Found {len(amounts)} Duffel offer(s) (median "
                        f"{supplier_median:,.2f} {supplier_currency}) but could not convert to "
                        f"{claim.currency}; manual review required."
                    ),
                    raw_response=data,
                    status_override=STATUS_NEEDS_MANUAL_REVIEW,
                )
            converted, rate = supplier_median, 1.0

        live_note = (
            "" if (request_data or {}).get("live_mode") else " (test mode: synthetic fares)"
        )
        fx_note = (
            f" [{supplier_currency}->{claim.currency} @ {rate:.4f}]"
            if rate and supplier_currency != claim.currency.upper()
            else ""
        )
        return ProviderBenchmarkResult(
            provider_name=self.provider_name,
            reference_amount=round(converted, 2),
            provider_reference_id=(request_data or {}).get("id"),
            confidence=0.9 if (request_data or {}).get("live_mode") else 0.55,
            reason=(
                f"Median of {len(amounts)} Duffel offer(s) for {origin}->{destination} on "
                f"{departure_date}: {supplier_median:,.2f} {supplier_currency} "
                f"= {converted:,.2f} {claim.currency}{fx_note}.{live_note}"
            ),
            raw_response=data,
        )


class DuffelStaysProvider:
    """Real per-stay hotel benchmark via Duffel Stays (POST /stays/search).

    Median ``cheapest_rate_total_amount`` for the city + dates is FX-converted to
    the claim currency. Needs coordinates (metadata latitude/longitude, or a known
    Indian city name) and a check-in date; check-out defaults to check-in + nights
    (metadata ``nights``, default 1). The benchmark is the total for the stay.
    """

    provider_name = "duffel_stays"

    def fetch_benchmark(self, claim: "ClaimEvidenceInput") -> "ProviderBenchmarkResult":
        from app.evidence_verification.service import (
            STATUS_NEEDS_MANUAL_REVIEW,
            ProviderBenchmarkResult,
            ProviderUnavailableError,
        )

        if not settings.DUFFEL_API_KEY:
            raise ProviderUnavailableError("DUFFEL_API_KEY is not configured.")

        lat, lon = self._resolve_coords(claim)
        check_in = claim.service_date or claim.invoice_date
        if lat is None or lon is None or not check_in:
            missing = []
            if lat is None or lon is None:
                missing.append("latitude/longitude (or a known city)")
            if not check_in:
                missing.append("check_in date")
            return ProviderBenchmarkResult(
                provider_name=self.provider_name,
                reference_amount=None,
                provider_reference_id=None,
                confidence=0.4,
                reason=(
                    "Hotel rate lookup needs a location and check-in date. Missing: "
                    f"{', '.join(missing)}."
                ),
                raw_response={"missing_fields": missing},
                status_override=STATUS_NEEDS_MANUAL_REVIEW,
            )

        nights = _int_from_metadata(claim.metadata, "nights", 1)
        check_out = claim.metadata.get("check_out_date") or self._add_days(check_in, nights)
        rooms = _int_from_metadata(claim.metadata, "rooms", 1)
        guests = _int_from_metadata(claim.metadata, "guests", 1)
        radius = _int_from_metadata(claim.metadata, "radius_km", 5)

        payload = {
            "data": {
                "rooms": rooms,
                "location": {
                    "radius": radius,
                    "geographic_coordinates": {"longitude": lon, "latitude": lat},
                },
                "guests": [{"type": "adult"}] * guests,
                "check_in_date": check_in,
                "check_out_date": check_out,
            }
        }
        base_url = (settings.DUFFEL_API_BASE_URL or "https://api.duffel.com").rstrip("/")
        url = f"{base_url}/stays/search"

        try:
            response = requests.post(
                url,
                json=payload,
                headers=_duffel_headers(),
                timeout=settings.DUFFEL_HTTP_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:  # noqa: BLE001
            raise ProviderUnavailableError(
                f"Duffel Stays search failed for ({lat},{lon}): {exc}"
            ) from exc

        results = (data.get("data") if isinstance(data, dict) else {}) or {}
        results = results.get("results") or []
        amounts = [
            float(r["cheapest_rate_total_amount"])
            for r in results
            if isinstance(r, dict) and r.get("cheapest_rate_total_amount") is not None
        ]
        if not amounts:
            return ProviderBenchmarkResult(
                provider_name=self.provider_name,
                reference_amount=None,
                provider_reference_id=None,
                confidence=0.4,
                reason=(
                    f"Duffel Stays returned no properties near ({lat},{lon}) for {check_in}"
                    f"->{check_out}. In test mode inventory is limited; verify manually."
                ),
                raw_response=data,
                status_override=STATUS_NEEDS_MANUAL_REVIEW,
            )

        supplier_currency = str(
            (results[0].get("cheapest_rate_currency") or "GBP")
        ).upper()
        supplier_median = _median(amounts)

        try:
            converted, rate = _frankfurter_convert(
                supplier_median,
                supplier_currency,
                claim.currency,
                settings.EVIDENCE_VERIFICATION_PROVIDER_TIMEOUT_SECONDS,
            )
        except Exception:  # noqa: BLE001
            if supplier_currency != claim.currency.upper():
                return ProviderBenchmarkResult(
                    provider_name=self.provider_name,
                    reference_amount=None,
                    provider_reference_id=None,
                    confidence=0.4,
                    reason=(
                        f"Found {len(amounts)} propertie(s) (median {supplier_median:,.2f} "
                        f"{supplier_currency}) but could not convert to {claim.currency}; "
                        "manual review required."
                    ),
                    raw_response=data,
                    status_override=STATUS_NEEDS_MANUAL_REVIEW,
                )
            converted, rate = supplier_median, 1.0

        fx_note = (
            f" [{supplier_currency}->{claim.currency} @ {rate:.4f}]"
            if rate and supplier_currency != claim.currency.upper()
            else ""
        )
        return ProviderBenchmarkResult(
            provider_name=self.provider_name,
            reference_amount=round(converted, 2),
            provider_reference_id=f"{lat},{lon}:{check_in}->{check_out}",
            confidence=0.85,
            reason=(
                f"Median cheapest rate across {len(amounts)} propertie(s) for {check_in}"
                f"->{check_out} ({nights} night(s)): {supplier_median:,.2f} {supplier_currency} "
                f"= {converted:,.2f} {claim.currency}{fx_note} (total for the stay)."
            ),
            raw_response=data,
        )

    def _resolve_coords(
        self, claim: "ClaimEvidenceInput"
    ) -> tuple[float | None, float | None]:
        lat = _to_float(claim.metadata.get("latitude") or claim.metadata.get("lat"))
        lon = _to_float(claim.metadata.get("longitude") or claim.metadata.get("lon") or claim.metadata.get("lng"))
        if lat is not None and lon is not None:
            return lat, lon
        city_source = (
            claim.location
            or claim.metadata.get("city")
            or claim.metadata.get("location")
            or ""
        )
        city = str(city_source).strip().lower()
        if city in _INDIA_CITY_COORDS:
            return _INDIA_CITY_COORDS[city]
        return None, None

    @staticmethod
    def _add_days(iso_date: str, days: int) -> str:
        try:
            base = datetime.strptime(iso_date[:10], "%Y-%m-%d")
            return (base + timedelta(days=max(days, 1))).strftime("%Y-%m-%d")
        except (TypeError, ValueError):
            return iso_date
