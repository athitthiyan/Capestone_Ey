# Skeptic Engine — Demo Storytelling: Requirements

**Spec version:** 1.0  
**Date:** 2026-07-06  
**Author:** Kiro (spec-driven generation)  
**Audience:** Client / Product Demo (enterprise audit & finance buyer)  
**Runtime target:** ~10 minutes (14 scenes) · 5-minute elevator cut (Scenes 01, 04, 06, 10, 12, 14)

---

## 1. Overview

This spec governs the interactive, animated, and cinematic elements of the Skeptic Engine product demo. The demo is not a feature tour — it is a story: an internal auditor's journey from anxious sampling to confident, full-coverage investigation.

### 1.1 The story in one sentence

> Traditional audit samples ~5% of transactions and hopes. Skeptic Engine investigates 100% — giving every flagged transaction an adversarial trial, a cited evidence file, a human sign-off, and a tamper-evident record.

### 1.2 Emotional throughline

Unease → Curiosity → Delight → Belief → Action

Each scene must move the audience one step along that arc. No scene is neutral.

### 1.3 Signature moments

| Priority | Scene | Name | Why it matters |
|----------|-------|------|----------------|
| P0 | 06 | Challenger vs. Defender debate | The one thing competitors don't have. The memorable beat. |
| P0 | 10 | Live product walkthrough | Proof it's real. Replaces all claims with evidence. |
| P1 | 01 | Cold open / particle field | Creates urgency and frames the 95% blind spot. |
| P1 | 14 | Close / CTA | Converts the demo into the next conversation. |
| P2 | 09 | Audit chain | The compliance/trust anchor for enterprise buyers. |

### 1.4 Call to action

**"Let's run it on your data. Where should we start?"**

---

## 2. Stakeholders & User Stories

### 2.1 Primary audience: enterprise audit/finance buyer

**US-01** As an audit director, I want to see that Skeptic Engine covers 100% of flagged transactions so that I can understand the coverage gap vs. my current process.

**US-02** As a compliance officer, I want to see an immutable, hash-chained audit trail so that I can be confident we can "show our work" to regulators.

**US-03** As a risk manager, I want to see the Challenger vs. Defender debate so that I can trust the system is pressure-testing claims, not rubber-stamping them.

**US-04** As a CFO evaluating the platform, I want to see the before/after business impact (5% → 100%, hours → minutes) so that I can justify the investment.

**US-05** As a demo attendee, I want the presentation to feel like a premium enterprise product, not a slide deck, so that I believe this is production-grade software.

### 2.2 Secondary audience: presenter / sales engineer

**US-06** As the presenter, I want scene-level timing cues, narration beats, and a 5-minute cut option so that I can adapt to any meeting length without losing the story arc.

**US-07** As the presenter, I want a recorded fallback of Scene 10 so that a network failure on stage doesn't break the demo.

---

## 3. Scene Inventory

All 14 scenes from the narration script and storyboard bible, with act, timing, style, and status.

| # | Scene name | Act | Timing | Style archetype | 5-min cut |
|---|-----------|-----|--------|----------------|-----------|
| 01 | Cold open — the 95% blind spot | Problem | 0:00–0:40 | Netflix documentary cold open | ✓ |
| 02 | Sampling is hope wearing a lab coat | Problem | 0:40–1:20 | Apple keynote problem framing | — |
| 03 | What the blind spot costs | Problem (stakes) | 1:20–2:00 | TED 'the stakes' beat | — |
| 04 | What if every transaction got a fair trial? | Vision | 2:00–2:40 | Apple product reveal | ✓ |
| 05 | Meet the crew — six specialists | Product intro | 2:40–3:30 | Google I/O system reveal | — |
| 06 | The debate: Challenger vs. Defender | Signature moment | 3:30–4:30 | OpenAI Dev Day 'wow' demo | ✓ |
| 07 | Every claim, cited | Grounding | 4:30–5:15 | Stripe Sessions credible detail | — |
| 08 | The confidence gate | Human-in-the-loop | 5:15–6:00 | AWS re:Invent flow explainer | — |
| 09 | An audit trail you can't argue with | Compliance | 6:00–6:40 | Enterprise trust beat | — |
| 10 | The product, end to end | Live product | 6:40–7:40 | Product-demo walkthrough | ✓ |
| 11 | One click, a whole pipeline | Behind the scenes | 7:40–8:20 | Microsoft Build architecture reveal | — |
| 12 | From 5% sampled to 100% investigated | Business impact | 8:20–9:00 | Investor impact slide | ✓ |
| 13 | The roadmap: from investigator to copilot | Future vision | 9:00–9:35 | Keynote 'what's next' | — |
| 14 | Put your ledger on trial — CTA | Close | 9:35–10:00 | Apple keynote close | ✓ |

---

## 4. Functional Requirements

### 4.1 Scene-level animation (all scenes)

**REQ-ANIM-01** Each scene must have exactly one "hero" animation (the signature move defined per scene in the storyboard bible). All supporting elements use quiet fade/rise.

**REQ-ANIM-02** Entrance animations must use ease-out cubic `(0.16, 1, 0.3, 1)`. Meters and camera effects use ease-in-out. Interactive/spring elements use physics-based springs.

**REQ-ANIM-03** Duration budget: micro-interactions ≤200ms, card/reveal animations 400ms, hero animations 800ms–1.5s. No single transition may exceed 1.5s.

**REQ-ANIM-04** Sibling element stagger must be 120ms.

**REQ-ANIM-05** Every animation must provide a `prefers-reduced-motion` fallback (cross-fade instead of motion).

### 4.2 Scene 01 — Cold open

**REQ-01-01** Display a dark navy (`#0B1220`) particle field with transaction rows drifting upward. Only ~5% of particles are lit blue; the rest are grey and fade into the dark.

**REQ-01-02** Title "EVERY TRANSACTION IS A QUESTION NO ONE HAS TIME TO ASK" renders in Inter Display 44pt with blur-to-focus entrance over 1.5s.

**REQ-01-03** An animated stat "~5% sampled" fades into the lower-right corner during the narration beat.

**REQ-01-04** The particle loop runs for the full 40s scene duration (looping at ~12s interval).

### 4.3 Scene 04 — Vision reveal

**REQ-04-01** Implement a "day-break wipe" transition from dark (Scene 03) to light that is reusable as a named Tailwind / CSS animation.

**REQ-04-02** The Skeptic Engine wordmark assembles from the particle field over 1.5s — the same particles that were "lost transactions" in Scene 01 converge to form the logo.

**REQ-04-03** A soft radial bloom effect follows the wordmark assembly.

### 4.4 Scene 05 — Agent crew (React Flow)

**REQ-05-01** Render the six agent nodes (Supervisor, Evidence, Challenger, Defender, Adjudicator, Verifier) in a radial layout around a central Case node using React Flow (already a project dependency).

**REQ-05-02** Each agent node uses the correct Lucide icon in a soft-tinted circle (Challenger = red circle, Defender = emerald circle, others = blue circle).

**REQ-05-03** Connecting edges draw sequentially in narration order (600ms strokeDashoffset animation per edge).

**REQ-05-04** Accept an `activeAgent` prop that highlights one node with a box-shadow ring and 1.03 scale.

**REQ-05-05** Below 768px: collapse the React Flow graph to a 2×3 card grid.

**REQ-05-06** Provide a text-list alternative for screen readers (`role="list"` with agent name + role).

### 4.5 Scene 06 — The debate (SIGNATURE)

**REQ-06-01** The `DebateViewer` must display Challenger arguments on the left (red/danger theme) and Defender arguments on the right (emerald/success theme) in a CSS grid `1fr auto 1fr`.

**REQ-06-02** Arguments stream in as typed text (character-by-character or word-by-word), staggered 120ms between messages.

**REQ-06-03** An animated `ConfidenceMeter` (0–1) sits between the two columns. It must update with a spring (stiffness 120, damping 18) as each argument lands.

**REQ-06-04** The Adjudicator `VerdictCard` reveals last with a scale `0.96→1.0` entrance and a gavel-impact ripple effect.

**REQ-06-05** Support `streaming`, `idle`, `round-1`, `round-2`, `adjudicated`, and `error` states.

**REQ-06-06** Each message must support `pending`, `typed`, and `cited` sub-states.

**REQ-06-07** On mobile (<768px), stack the columns vertically; the meter becomes a horizontal bar above the verdict.

**REQ-06-08** `aria-live="polite"` on the transcript container; `role="log"`; meter has `aria-valuenow`, `aria-valuemin`, `aria-valuemax`; honor `prefers-reduced-motion`.

**REQ-06-09** The demo must be playable with a static fixture (no live backend required for the Canva/pptx demo context). A `demoMode` prop enables the pre-scripted Maelstrom vs. Mabiku case.

### 4.6 Scene 07 — Evidence & citations

**REQ-07-01** Render an evidence file with claims on the left and source chips on the right. Animated threads connect each claim to its source (Policy KB, FX API, Vendor Registry).

**REQ-07-02** One claim is pre-marked as `unsupported` — it shakes and greys out with a red strike-through label "Verifier rejected".

**REQ-07-03** The thread-draw animation completes in ≤600ms per claim.

### 4.7 Scene 08 — Confidence gate

**REQ-08-01** Implement a `ConfidenceGate` component with a branching SVG path and three lanes: Auto-clear (≥0.90, success/emerald), Human review (0.70–0.90, warning/amber), Escalate (<0.70, danger/red).

**REQ-08-02** A case token animates along the SVG path (offset-path, 900ms ease-in-out) and routes to the lane matching the `confidence` prop.

**REQ-08-03** The active lane pulses on token arrival.

**REQ-08-04** Thresholds must be shown as a visible legend with both color and text labels (no color-only encoding).

### 4.8 Scene 09 — Audit chain

**REQ-09-01** Implement an `AuditChain` component that renders hash-chained record blocks vertically with 12px connectors.

**REQ-09-02** Each block shows: event type, truncated hash, reference to previous hash, timestamp, actor.

**REQ-09-03** Support a `tampered` demo prop: the specified block turns red, its connector visually snaps, and an `aria-live` announcement fires.

**REQ-09-04** The component must virtualize for chains longer than 50 records.

**REQ-09-05** Blocks drop-in over 300ms on mount with the stagger rule.

### 4.9 Scene 10 — Live product

**REQ-10-01** The live demo flow must cover: CSV Intake → Dashboard (risk distribution, agent health) → Case Workspace (pipeline status + debate viewer) → Review Queue → Report export.

**REQ-10-02** A seeded demo case must be pre-loadable via a `?demo=1` query parameter (or equivalent dev mode) so no CSV upload is required on stage.

**REQ-10-03** A recorded fallback MP4 (20–30s) of the full flow must exist as a file in the repo (`/Docs/demo-recording.mp4` or equivalent) for use when live network is unreliable.

**REQ-10-04** Background WebSocket polling must be paused during the live demo run to prevent UI flicker (controlled by a demo mode flag).

### 4.10 Scene 12 — Business impact

**REQ-12-01** Render two donut charts side by side: "Before" (5% coverage, muted grey) and "After" (100% coverage, emerald). Both use Recharts (already a project dependency).

**REQ-12-02** Four stat cards count up from 0 to their final value over 1.2s ease-out on scroll-into-view.

**REQ-12-03** Stat values must be honest and defensible. Use these defaults until replaced by pilot data:
- Coverage: 5% → 100%
- Review time: Hours → Minutes (per case, for auto-cleared tier)
- Audit-ready decisions: 0% of samples → 100% of investigated cases
- Consistency: "Rules-based variance" → "Structured debate + citation"

### 4.11 Scene 14 — Close / CTA

**REQ-14-01** Return to the dark navy bookend from Scene 01. The Scene-01 particles return in a settled, calm constellation state.

**REQ-14-02** The CTA button "Book a live investigation" pulses once on appearance (scale 1.0 → 1.04 → 1.0, 400ms).

**REQ-14-03** The closing narration line "Let's run it on your data. Where should we start?" is displayed as on-screen text if presenting asynchronously.

---

## 5. Non-Functional Requirements

### 5.1 Performance

**REQ-NFR-01** All demo page routes must reach First Contentful Paint in ≤1.5s on a modern laptop with a live backend, and ≤2s with the seeded demo fixture.

**REQ-NFR-02** Particle animations must use CSS transforms and `will-change: transform` (or Canvas/WebGL) to prevent layout thrash.

**REQ-NFR-03** React Flow graph (Scene 05) must render in ≤200ms for 6 nodes.

### 5.2 Reliability

**REQ-NFR-04** The demo must be fully operable without a live backend using demo mode fixtures. No scene may show an error state in demo mode.

**REQ-NFR-05** The confidence gate (Scene 08) must clamp its `confidence` prop to [0, 1] and never render outside that range (fixes the known open issue from the audit report).

### 5.3 Accessibility

**REQ-NFR-06** All animated components must pass WCAG 2.1 AA contrast: body text ≥4.5:1, large text ≥3:1.

**REQ-NFR-07** Color must never be the sole means of conveying information (risk lanes, debate sides, claim status must all have text/icon pairs).

**REQ-NFR-08** All interactive elements must be keyboard-navigable and have visible focus rings.

### 5.4 Brand fidelity

**REQ-NFR-09** Every new component must consume existing Tailwind design tokens — `primary`, `success`, `warning`, `danger`, `info`, `shadow.card`, `shadow.panel`, `font-sans`, `font-mono`. No hard-coded hex values in component files.

**REQ-NFR-10** Lucide icons must be used throughout, at 1.5–2px stroke, inside soft-tinted circles at 2.5× the icon diameter.

**REQ-NFR-11** Red (`danger`) and emerald (`success`) must be reserved for Challenger/escalate and Defender/verified semantics respectively. They must not be used decoratively.

### 5.5 Maintainability

**REQ-NFR-12** Each hero component (DebateViewer, AgentCrew, ConfidenceGate, AuditChain) must be located in the feature folder closest to its domain and expose a clean, documented props interface.

**REQ-NFR-13** Demo fixture data must live in `/UI/data/demo/` as typed TypeScript fixtures, not inline in components.

---

## 6. Out of Scope

The following are out of scope for the storytelling spec but exist in the product roadmap (Scene 13):

- Real-time monitoring (continuous, not periodic)
- Audit copilot (natural-language Q&A over the audit log)
- ERP / GRC integrations
- Playbook marketplace
- AI voice-over track generation

These must be presented as roadmap items, clearly labeled "Coming next", and must not be implied as shipped capabilities in the live demo.

---

## 7. Acceptance

This spec is accepted when:
1. All scenes in the 5-minute cut (01, 04, 06, 10, 12, 14) have passing acceptance criteria (see `scene-acceptance-criteria.md`).
2. The demo can be run end-to-end with `?demo=1` without a live backend.
3. The debate signature moment (Scene 06) generates an audible room reaction in at least one rehearsal ("Have you ever seen AI argue with itself?").
4. The CTA is the last thing the audience sees, and it ends with a question.
