# Free APIs for Evidence Verification

Maps each `*_PROVIDER_URL` / `*_PROVIDER_API_KEY` env var in the evidence-verification
module to a recommended **free / free-tier** API, with limits, auth, and how to wire it in.
All categories are India/INR-focused (INR default currency, GSTIN validation).

Researched July 2026. Free tiers change — confirm limits at signup.

---

## How integration actually works (read first)

Your `EvidenceVerificationService` picks a provider per category (`_provider_for`). Today only
`fx` uses a native keyless adapter (`FrankfurterFxProvider`). Every other category uses
`ConfiguredHttpBenchmarkProvider`, which **POSTs your internal claim payload** to the configured
URL and expects a JSON body back containing `reference_amount` (or `fetched_amount`/`amount`).

Real free APIs below **do not** speak that payload shape (most are `GET` with query params and
return their own JSON). So you have two integration paths:

- **Path A — thin wrapper (fast, keeps code unchanged).** Stand up a tiny endpoint per category
  (a FastAPI route, or a serverless function) that receives your claim payload, calls the real
  free API, and returns `{ "reference_amount": <number>, "reason": "...", "provider_reference_id": "..." }`.
  Point `*_PROVIDER_URL` at that wrapper.
- **Path B — native adapter (cleaner, recommended long-term).** Add a class in
  `app/evidence_verification/providers.py` like `FrankfurterFxProvider` (a `fetch_benchmark`
  returning `ProviderBenchmarkResult`) and route to it in `_provider_for`. No wrapper server.

Path B is the better fit for fuel, cab, and GST since those need per-category logic
(price × litres, distance × rate, identity validity).

---

## Category-by-category picks

### ⛽ Fuel — `FUEL_PRICE_PROVIDER_URL` / `_API_KEY`
Strongest free options of the set. Benchmark = `price_per_litre × claimed litres`.

- **PurePriceIO** — real-time petrol/diesel/LPG by state & city, 200 free credits, no card. Best pick.
- **IndianAPI Fuel Price API** (indianapi.in) — daily city prices, free tier.
- **fuel-prices-india-api** (GitHub, anshikakaythwas) — open-source scraper you self-host; fully free, no quota.

Your code already parses litres from the description (`quantity_match`), so a native adapter can
do `reference_amount = rate_per_litre(city, date) × quantity` cleanly.

### ✈️ Flight — two separate concerns: existence vs. price
Flight verification splits in two, because **no single free API does both well**:

**1. Route existence (WIRED) — Aviationstack, `FLIGHT_VALIDATION_*`.**
Aviationstack returns schedules/tracking, **not fares**. It's wired as a native
`AviationstackFlightProvider` that hits `/routes` to confirm a route genuinely exists
(VERIFIED) or not (FLAGGED) — catching fabricated flights. It needs **IATA codes**
(`dep_iata`/`arr_iata` in metadata, e.g. MAA/DEL), not city names, and returns no amount.
Free tier ~100 requests/month, `access_key` query param.

**2. Price benchmark (FOLLOW-UP) — `FLIGHT_PRICE_PROVIDER_URL`.**
To actually check a claimed airfare against market fares, add a dedicated fares API. When
`FLIGHT_PRICE_PROVIDER_URL` is set it takes precedence over the Aviationstack validator.
- **Kiwi.com Tequila** — free API key, real fare search. **Recommended durable pick.**
- **Duffel** — free to start, real fares; the practical migration target off Amadeus.
- Amadeus **Flight Offers Search** — best data, but ⚠️ **Self-Service sunsets July 17, 2026**; stopgap only.

Benchmark = median offered fare for route + date. Needs `route_from`, `route_to`, `service_date`.

### 🏨 Hotel — `HOTEL_PRICE_PROVIDER_URL` / `_API_KEY`
Free hotel *price* APIs are scarce (most are partner/commercial).

- **Amadeus Hotel Search** — free test tier, 150k+ hotels — but same **Jul 17, 2026 sunset**. Stopgap only.
- **Duffel Stays** — free to start, durable alternative.
- Fallback: a **city per-night policy cap table** (like a per-diem) when no live API is available —
  cheap, deterministic, and audit-friendly.

Needs `location` + a stay date (validator requires these).

### 🚕 Cab — `CAB_FARE_PROVIDER_URL` / `_API_KEY`
No official free Ola/Uber fare API (Uber's price endpoint is deprecated/partner-gated; third-party
calculators aren't APIs). Compute it instead:

- **OSRM** (project-osrm.org demo server) or **OpenRouteService** (free key, self-hostable) →
  get **distance_km** between pickup/drop.
- Apply a **local rate card**: `base + per_km × distance (+ per_min × duration)`.

Your validator already accepts either `distance_km` in metadata or pickup/drop, so a native adapter
that geocodes → routes → applies the rate card is the right shape. Self-hosting OSRM removes quotas.

### 🍽️ Food — `FOOD_BENCHMARK_PROVIDER_URL` / `_API_KEY`
Weakest category for free live data.

- **Numbeo Data API** — has "Meal, Inexpensive Restaurant" and mid-range meal prices per city
  (low/avg/high). Requires an API key; low-cost rather than truly free — check current tier.
- **Recommended pragmatic default:** a **per-meal / per-diem policy table** by city tier
  (metro / tier-1 / tier-2). Deterministic, no external dependency, and matches how expense
  policies actually cap meals. Use Numbeo only if you want market-rate benchmarking.

### 🧾 GST — `GST_VERIFICATION_PROVIDER_URL` / `_API_KEY`
Note: GST verification is about **vendor identity validity**, not price — your `EVIDENCE_VERIFICATION_GST_TOLERANCE=0.0`
reflects an exact-match/validity check. Format validation already happens locally (`_is_valid_gstin`);
the API confirms the GSTIN is real and active on the GST portal.

- **GSTINCheck** (gstincheck.co.in) — free API key by email, ~20 free test requests; returns legal name,
  status, registration date.
- **Bulkpe** — free GST lookup tool + API.
- **Masters India** — one free GSTIN search.
- **eKYCNow** — 5 free verifications on signup, no card.
- The **official GST portal** (services.gst.gov.in) allows manual checks but has **no public API**.

A native adapter should treat "GSTIN active + legal name matches vendor" as VERIFIED, "not found /
cancelled" as FLAGGED — not an amount comparison.

---

## Recommended starting set (all genuinely free)

| Category | Pick | Free tier | Auth | Status |
|---|---|---|---|---|
| Fuel | IndianAPI Fuel Price | free tier | `x-api-key` | ✅ wired (native adapter) |
| Flight (existence) | Aviationstack `/routes` | ~100/mo | `access_key` | ✅ wired (fallback validator) |
| Flight (price) | Duffel `/air/offer_requests` | test/live key | Bearer + version | ✅ wired (real fares, FX-converted) |
| Hotel | Duffel Stays `/stays/search` | test/live key | Bearer + version | ✅ wired (per-stay rate, FX-converted) |
| Cab | OSRM/OpenRouteService + rate card | Free / self-host | None / key | ⬜ todo |
| Food | Per-diem table (or Numbeo) | n/a | — | ⬜ todo |
| GST | GSTINCheck | ~20 free | path key | ✅ wired (native validity check) |
| FX | Frankfurter | Unlimited | None | ✅ wired |

Suggested rollout order: **Fuel → GST → Cab** (best free data / most deterministic), then
**Flight → Hotel** (watch the Amadeus sunset), and treat **Food** as a policy-table default.

---

## Sources
- GST: [GSTINCheck](https://gstincheck.co.in/), [Bulkpe](https://bulkpe.in/check-gst), [Masters India](https://www.mastersindia.co/gst-number-verification-api-bulk-utility/), [Message Central 2026 guide](https://www.messagecentral.com/blog/gst-verification-api-india), [GST portal](https://services.gst.gov.in/services/searchtp)
- Flight: [Thunderbit — flight APIs with free tiers](https://thunderbit.com/blog/best-flight-api-with-free-tiers), [Amadeus Flight Offers Search](https://developers.amadeus.com/self-service/category/flights/api-doc/flight-offers-search), [Aviationstack pricing](https://aviationstack.com/pricing), [Kiwi Tequila guide](https://phptravels.com/blog/comprehensive-guide-to-flights-api-integration)
- Hotel: [Amadeus Hotel Search](https://developers.amadeus.com/self-service/category/hotels/api-doc/hotel-search), [API.market travel APIs 2026](https://api.market/blog/magicapi/travel-api/best-travel-apis-for-developers)
- Fuel: [PurePriceIO](https://purepriceio.com/), [IndianAPI Fuel Price](https://indianapi.in/fuel-price-api), [fuel-prices-india-api (GitHub)](https://github.com/anshikakaythwas/fuel-prices-india-api)
- Cab: [OSRM Table API](https://blog.afi.io/blog/osrm-table-api-free-and-open-source-distance-matrix-api/), [OpenRouteService](https://github.com/giscience/openrouteservice), [Uber Prices API](https://developer.uber.com/docs/v1-estimates-price)
- Food: [Numbeo API](https://www.numbeo.com/common/api.jsp), [Numbeo restaurant prices](https://www.numbeo.com/cost-of-living/prices_by_city.jsp?itemId=1)
