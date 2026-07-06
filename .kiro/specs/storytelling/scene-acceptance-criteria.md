# Skeptic Engine — Scene-by-Scene Acceptance Criteria

**Spec version:** 1.0  
**Date:** 2026-07-06  
**Format:** BDD-style (Given / When / Then). Each criterion maps to a requirement in `requirements.md`.

---

## How to use this document

- **P0** criteria are required for the 5-minute cut demo to be considered shippable.
- **P1** criteria are required for the full 10-minute deck.
- **P2** criteria are polish/accessibility gating items.
- ✓ = must pass before merge. Verify manually in demo mode (`?demo=1&cut=5min`).

---

## Scene 01 — Cold open "The 95% blind spot"

**Priority:** P0 | **Duration:** 0:00–0:40

### AC-01-01 — Particle field renders ✓
**Given** the demo route is opened at `/demo?demo=1`  
**When** Scene 01 becomes active  
**Then** a canvas element fills the full viewport with upward-drifting particles on a `#0B1220` navy background  
**And** approximately 5% of particles are lit blue, the rest are grey  
**And** the animation runs continuously without visible jank or layout shift

### AC-01-02 — Title entrance ✓
**Given** Scene 01 is active  
**When** the scene enters  
**Then** the title "EVERY TRANSACTION IS A QUESTION NO ONE HAS TIME TO ASK" renders in Inter 44pt bold, white  
**And** the title enters with a blur-to-focus animation over 1.5s  
**And** the subtitle line "Your audit team looked at maybe five percent of them." fades in 500ms after the title

### AC-01-03 — Stat callout ✓
**Given** the title has finished its entrance  
**When** 2 seconds have elapsed since scene entry  
**Then** a "~5% sampled" label fades into the lower-right quadrant of the scene  
**And** the label uses Inter 13pt uppercase tracking

### AC-01-04 — Reduced motion ✓
**Given** the user's OS has `prefers-reduced-motion: reduce` set  
**When** Scene 01 becomes active  
**Then** the particle canvas is replaced with a static `#0B1220` gradient background  
**And** the title appears at full opacity with no blur animation  
**And** the stat callout appears immediately

### AC-01-05 — Emotional target ✓
*Verification: presenter self-report during rehearsal*  
**Given** a demo observer watches Scene 01 cold (no prior context)  
**When** the scene completes  
**Then** the observer can articulate "there's a huge blind spot in audit sampling"

---

## Scene 02 — "Sampling is hope wearing a lab coat"

**Priority:** P1 | **Duration:** 0:40–1:20

### AC-02-01 — Three pain cards animate in
**Given** Scene 02 is active  
**When** the scene enters  
**Then** three frosted-glass cards (Manual & Slow, False Positives, Missed Fraud) slide in from the left with a 120ms stagger  
**And** each card has: a colored icon in a soft circle, a bold header, and a 2-line description

### AC-02-02 — Iceberg reveals last
**Given** the three cards have entered  
**When** the stagger completes  
**Then** the iceberg card's underwater mass fades up as the last element  
**And** the iceberg visual communicates that the hidden portion is far larger than the visible portion

### AC-02-03 — Icon semantics
**Given** Scene 02 is visible  
**When** inspected visually and with a screen reader  
**Then** the clock icon has `aria-label="Manual and slow"`  
**And** the alarm icon has `aria-label="False positives"`  
**And** the iceberg icon has `aria-label="Missed fraud"` (not color-only)

---

## Scene 03 — "What the blind spot costs"

**Priority:** P1 | **Duration:** 1:20–2:00

### AC-03-01 — Three stat callouts count up
**Given** Scene 03 is active  
**When** the scene enters and the stats come into view  
**Then** three large stat numerals count up from 0 to their final values over 1.2s ease-out  
**And** the exposure figure uses `text-danger-foreground`

### AC-03-02 — Regulator letter watermark
**Given** Scene 03 is active  
**When** the scene enters  
**Then** a faint letter-shaped watermark (opacity ~8%) drifts up 3% behind the stat numbers  
**And** the main stat numerals remain clearly legible (contrast ≥7:1 against the watermark)

### AC-03-03 — Audience engagement cue
**Given** Scene 03 is active and notes mode is on (`?notes=1`)  
**When** the scene is displayed  
**Then** the speaker notes overlay shows: "Audience: 'Any of this sound familiar?'"

---

## Scene 04 — "What if every transaction got a fair trial?" (Vision)

**Priority:** P0 | **Duration:** 2:00–2:40

### AC-04-01 — Day-break wipe transition ✓
**Given** Scene 04 becomes active (immediately after Scene 03 which is dark)  
**When** the transition plays  
**Then** the scene background wipes from `#0B1220` to `#F5F7FB` left-to-right over 800ms ease-in-out  
**And** the wipe is implemented as a reusable CSS animation class `animate-day-break`

### AC-04-02 — Particle convergence ✓
**Given** the day-break wipe completes  
**When** the light scene is fully revealed  
**Then** particles visually converge toward the center of the viewport over 1.5s  
**And** the Skeptic Engine wordmark assembles/fades in at the convergence point

### AC-04-03 — Logo and tagline ✓
**Given** particle convergence completes  
**When** the wordmark is visible  
**Then** the tagline "Every transaction gets a fair trial." fades in 400ms after the wordmark  
**And** the wordmark and tagline are horizontally centered  
**And** text contrast against the light background is ≥4.5:1

### AC-04-04 — Music note in speaker notes ✓
**Given** notes mode is active  
**When** Scene 04 is visible  
**Then** the speaker notes read: "Music lifts. Particles converge into the logo. This is Skeptic Engine."

---

## Scene 05 — "Meet the crew — six specialists"

**Priority:** P1 | **Duration:** 2:40–3:30

### AC-05-01 — Six agent nodes render
**Given** Scene 05 is active  
**When** the React Flow diagram mounts  
**Then** six agent nodes render around a central Case node in a radial layout  
**And** each node shows: the agent's Lucide icon in a colored circle, name, and role caption

### AC-05-02 — Correct color identity
**Given** the crew diagram is visible  
**When** the Challenger and Defender nodes are inspected  
**Then** Challenger has a red/danger-tinted icon circle  
**And** Defender has an emerald/success-tinted icon circle  
**And** all other agents have a blue/primary-tinted icon circle

### AC-05-03 — Sequential edge draw
**Given** Scene 05 is active and `animateEdges={true}`  
**When** the scene enters  
**Then** edges draw in narration order (Supervisor first, Verifier last), 600ms per edge, 200ms stagger  
**And** edges start at the central Case node and extend to each satellite

### AC-05-04 — `activeAgent` prop highlights
**Given** the crew diagram renders with `activeAgent="Challenger"`  
**When** the diagram is visible  
**Then** the Challenger node has a primary ring and 1.03 scale  
**And** all other nodes are at their default visual state

### AC-05-05 — Mobile responsive
**Given** the viewport is <768px  
**When** Scene 05 is active  
**Then** the React Flow graph is hidden  
**And** a 2×3 grid of plain agent cards renders in its place  
**And** all 6 agents are visible with correct names, roles, and icon colors

### AC-05-06 — Screen reader alternative
**Given** an assistive technology user navigates to Scene 05  
**When** the diagram is inspected  
**Then** a `role="list"` element contains one `role="listitem"` per agent  
**And** each item describes the agent's name and role in plain text

---

## Scene 06 — "The debate: Challenger vs. Defender" (SIGNATURE)

**Priority:** P0 | **Duration:** 3:30–4:30

This scene must generate a "Have you ever seen AI do this?" reaction. Every criterion here is P0.

### AC-06-01 — Split layout with live confidence meter ✓
**Given** Scene 06 is active in demo mode  
**When** the scene renders  
**Then** Challenger arguments appear on the left in a `danger`-themed column  
**And** Defender arguments appear on the right in a `success`-themed column  
**And** a `ConfidenceMeter` (0–1) is visible between the two columns  
**And** the grid is `grid-cols-[1fr_auto_1fr]` on desktop

### AC-06-02 — Word-by-word message streaming ✓
**Given** Scene 06 is active in demo mode with `streamMessages={true}`  
**When** a new argument enters  
**Then** the argument summary text appears word-by-word at a 60ms interval  
**And** once the full text is revealed, citation badges animate in  
**And** there is a 120ms delay before the next argument begins streaming

### AC-06-03 — Confidence meter follows the debate ✓
**Given** the debate is streaming  
**When** each argument completes  
**Then** the ConfidenceMeter updates to its scripted value with a spring animation (stiffness 120, damping 18)  
**And** the sequence is: 0.5 → 0.42 (after Challenger 1) → 0.61 (Defender 1) → 0.55 (Challenger 2) → 0.78 (Defender 2) → 0.83 (verdict)  
**And** the meter's needle is visibly dragged back toward risk and then recovered

### AC-06-04 — Adjudicator verdict card with gavel ✓
**Given** all four debate arguments have completed  
**When** the verdict argument streams in  
**Then** the `VerdictCard` enters with `scale-95→scale-100` + `opacity-0→opacity-100` over 400ms  
**And** the Gavel icon animates: rotates 0°→−15°→0° with spring physics  
**And** the verdict confidence value (0.83) is displayed in the ConfidenceMeter after a 200ms hold  
**And** the verdict text reads "Cleared with conditions — Vendor legitimate; FX claim revised; recommend monitoring for 90 days."

### AC-06-05 — State machine ✓
**Given** the demo debate fixture is loaded  
**When** inspecting the component state  
**Then** the valid states are: `idle`, `streaming-challenger-1`, `streaming-defender-1`, `streaming-challenger-2`, `streaming-defender-2`, `streaming-verdict`, `adjudicated`  
**And** the `error` state renders a graceful fallback message, not a thrown exception

### AC-06-06 — Mobile layout ✓
**Given** the viewport is <768px  
**When** Scene 06 is active  
**Then** the columns stack vertically: Challenger on top, Defender below  
**And** the ConfidenceMeter renders as a horizontal bar above the VerdictCard  
**And** all arguments remain readable

### AC-06-07 — Accessibility ✓
**Given** an assistive technology user navigates Scene 06  
**When** messages stream in  
**Then** the transcript container has `aria-live="polite"` and `role="log"`  
**And** the ConfidenceMeter has `aria-valuenow`, `aria-valuemin="0"`, `aria-valuemax="1"`, `aria-label="Verdict confidence"`  
**And** each column heading ("Challenger view", "Defender view") is a visible `<h2>` with semantic role  
**And** the debate sides are labeled with both text and color (not color-only)

### AC-06-08 — Reduced motion ✓
**Given** `prefers-reduced-motion: reduce` is set  
**When** Scene 06 plays  
**Then** arguments appear at full opacity immediately (no word-by-word typing)  
**And** the meter jumps to target values without spring animation  
**And** the gavel icon appears without rotation animation

### AC-06-09 — Audience CTA in notes ✓
**Given** notes mode is active  
**When** Scene 06 reaches the verdict  
**Then** the speaker notes overlay shows: "Audience: 'Have you ever seen AI argue with itself before?'"

---

## Scene 07 — "Every claim, cited"

**Priority:** P1 | **Duration:** 4:30–5:15

### AC-07-01 — Evidence file renders with citation threads
**Given** Scene 07 is active  
**When** the scene enters  
**Then** four evidence claims render on the left  
**And** four source chips render on the right (Policy KB, FX Rate API, Vendor Registry, Contract Archive)  
**And** SVG threads animate from each claim to its source chip, 400ms per thread, 100ms stagger

### AC-07-02 — Unsupported claim rejection
**Given** the citation threads have finished drawing  
**When** the FX Rate API claim is rendered  
**Then** that claim has an `unsupported` visual state  
**And** the claim shakes (translate-x ±4px, 3 cycles, 300ms)  
**And** the claim text greys out to `text-muted-foreground`  
**And** a "Verifier rejected" badge in danger style appears on the claim  
**And** an `aria-live` region announces "Claim marked unsupported by Verifier"

### AC-07-03 — Presenter note
**Given** notes mode is active  
**When** the Verifier rejection plays  
**Then** the speaker notes read: "(Point at the struck-through claim.) Like that one. Unsupported — struck from the record."

---

## Scene 08 — "The confidence gate"

**Priority:** P1 | **Duration:** 5:15–6:00

### AC-08-01 — SVG gate renders with three lanes
**Given** Scene 08 is active  
**When** the gate renders  
**Then** three labeled lanes are visible: "Auto-clear ≥0.90", "Human review 0.70–0.90", "Escalate <0.70"  
**And** lanes are colored success/emerald, warning/amber, danger/red respectively  
**And** each lane has a text label AND an icon (not color-only)

### AC-08-02 — Token routing animation
**Given** `confidence={0.83}` is passed to the component  
**When** `animate={true}` and the scene is active  
**Then** a token travels the SVG path from the entry point to the "Human review" lane over 900ms  
**And** the token routing path uses `offset-path` CSS animation  
**And** on arrival, the amber lane pulses (ring animation, 400ms)

### AC-08-03 — Confidence clamping
**Given** a `confidence` prop outside [0,1] is passed  
**When** the component renders  
**Then** values >1 are clamped to 1.0  
**And** values <0 are clamped to 0.0  
**And** no visual anomaly or console error occurs

### AC-08-04 — Aria routing announcement
**Given** the token arrives at a lane  
**When** the routing completes  
**Then** an `aria-live="polite"` region announces: "Transaction routed to Human review — confidence 0.83"

---

## Scene 09 — "An audit trail you can't argue with"

**Priority:** P1 | **Duration:** 6:00–6:40

### AC-09-01 — Chain renders with 12 blocks
**Given** Scene 09 is active with the demo audit chain fixture  
**When** the chain mounts  
**Then** 12 hash-chained record blocks render vertically  
**And** blocks animate in with a 300ms drop-in, 120ms stagger  
**And** each block shows: event type icon, truncated hash (8 chars), previous hash reference, timestamp, actor

### AC-09-02 — Dark scene aesthetic
**Given** Scene 09 is active  
**When** the scene renders  
**Then** the background is dark navy (`#0B1220`)  
**And** hash text uses `font-mono` (JetBrains Mono)  
**And** block borders are `border-primary/30` (subtle blue)

### AC-09-03 — Tamper demonstration ✓ (P0 for live demos)
**Given** the chain is rendering in demo mode  
**When** the presenter presses the `T` key or the "Tamper" button is clicked  
**Then** block 6 transitions to `border-danger bg-danger-soft` with a shake animation  
**And** the connector between blocks 5 and 6 becomes a dashed red line with a `TriangleAlert` icon  
**And** an `aria-live="assertive"` region announces "Chain integrity broken at record 6"  
**And** all other blocks remain unchanged

### AC-09-04 — Presenter note
**Given** notes mode is active  
**When** Scene 09 is visible  
**Then** speaker notes read: "Change one record — [press T] — and the whole chain breaks."

---

## Scene 10 — "The product, end to end" (Live product)

**Priority:** P0 | **Duration:** 6:40–7:40

### AC-10-01 — Demo mode seeded flow ✓
**Given** the app is opened at `/?demo=1`  
**When** the user navigates the intake page  
**Then** the Maelstrom Corp GmbH case (TXN-2024-8842, $285,000) is pre-populated  
**And** no CSV upload is required to see the case  
**And** the dashboard shows the case in the investigations list

### AC-10-02 — Workspace pre-populated ✓
**Given** demo mode is active  
**When** the user opens the case workspace for `demo-case-001`  
**Then** the pipeline status shows `agent_debate` stage as active  
**And** the debate viewer shows the pre-scripted exchange (all 5 arguments)  
**And** the evidence tab shows the demo evidence sources  
**And** no API loading errors appear

### AC-10-03 — Background polling suppressed ✓
**Given** demo mode is active  
**When** the workspace is open  
**Then** WebSocket polling is paused (demo mode flag disables `use-investigation-realtime.ts` auto-reconnect)  
**And** no UI flicker occurs from background data refresh

### AC-10-04 — Route breadcrumb chips ✓
**Given** Scene 10 is active  
**When** the screen montage plays  
**Then** route chips label each screen as it appears: "1. Intake → 2. Dashboard → 3. Workspace → 4. Review → 5. Report"  
**And** the active chip is highlighted

### AC-10-05 — Recording fallback ✓
**Given** the Scene 10 component has `mode="recording"`  
**When** the scene is active  
**Then** a `<video>` element plays `demo-recording.mp4`  
**And** if the file doesn't exist, a styled placeholder with recording instructions is shown (not a broken video element)

---

## Scene 11 — "One click, a whole pipeline"

**Priority:** P1 | **Duration:** 7:40–8:20

### AC-11-01 — Pipeline conveyor renders
**Given** Scene 11 is active  
**When** the scene enters  
**Then** a horizontal pipeline renders: Intake → Evidence → Debate → Verify → Gate → Report → Audit  
**And** each stage has a label and icon  
**And** the background is dark navy

### AC-11-02 — Token animation
**Given** the scene is active  
**When** the animation plays  
**Then** a token travels left-to-right across the pipeline stages, lighting each one as it passes  
**And** infra icons (LangGraph, Postgres, Redis, Celery, Prometheus) pulse below their respective stages

### AC-11-03 — Infrastructure labels
**Given** the pipeline is visible  
**When** the infra icons render  
**Then** each has a `font-mono` text label  
**And** LangGraph appears below the Debate stage  
**And** Prometheus appears below the Report stage as a "watching cost & latency" label

---

## Scene 12 — "From 5% sampled to 100% investigated"

**Priority:** P0 | **Duration:** 8:20–9:00

### AC-12-01 — Before/After donut charts ✓
**Given** Scene 12 is active  
**When** the scene enters  
**Then** two donut charts render side by side: "Before" (5%, muted grey) and "After" (100%, emerald)  
**And** donuts animate from 0 to their target values over 500ms ease-out  
**And** the "Before" side uses `text-muted-foreground` labels  
**And** the "After" side uses `text-success-foreground` labels

### AC-12-02 — Four stat cards count up ✓
**Given** the stat cards enter the viewport  
**When** the intersection observer fires  
**Then** all four stat cards begin their count-up animation over 1.2s  
**And** the cards display: Coverage (5%→100%), Review time (Hours→Minutes), Audit decisions (Sampled→Full coverage), Defensibility (Rules-based→Cited & argued)  
**And** `prefers-reduced-motion` shows final values immediately

### AC-12-03 — Before/After are visually balanced ✓
**Given** Scene 12 renders on a 1920×1080 display  
**When** inspected visually  
**Then** the Before and After halves are equal width  
**And** the After half is visually dominant (larger text, richer color, more saturated)

### AC-12-04 — Stats are honest ✓
*Editorial criterion, verified by reviewer*  
**Given** the demo stat cards show specific claims  
**When** reviewed against the product's actual capabilities  
**Then** no stat claims a specific time reduction (e.g. "90% faster") that is not backed by pilot data  
**And** the "Review time" claim uses qualitative framing ("Hours → Minutes") not a specific multiplier

---

## Scene 13 — "The roadmap: from investigator to copilot"

**Priority:** P1 | **Duration:** 9:00–9:35

### AC-13-01 — Horizon timeline with 5 milestones
**Given** Scene 13 is active  
**When** the timeline renders  
**Then** 5 milestone nodes appear: Audit Copilot, Real-time Monitoring, Multi-model, Enterprise Integrations, Playbook Marketplace  
**And** nodes illuminate sequentially toward a vanishing point (200ms per node, 150ms stagger)

### AC-13-02 — Roadmap is clearly labeled as future
**Given** the timeline is visible  
**When** the milestones render  
**Then** the scene header reads "Coming Next" or "Roadmap"  
**And** no milestone is labeled with a shipped status  
**And** the speaker notes include: "These are roadmap items — shipped capabilities are in the demo you just saw."

---

## Scene 14 — "Put your ledger on trial" (Close / CTA)

**Priority:** P0 | **Duration:** 9:35–10:00

### AC-14-01 — Dark bookend ✓
**Given** Scene 14 becomes active  
**When** the scene renders  
**Then** the background is `#0B1220` (matching Scene 01)  
**And** the `ParticleField mode="settle"` renders a calm, sparse constellation  
**And** the visual bookend is perceptible: the audience recognizes the return to the opening aesthetic

### AC-14-02 — CTA text sequence ✓
**Given** Scene 14 is active  
**When** the text enters  
**Then** "Skeptic Engine." appears first  
**And** "Every transaction gets a fair trial — cited, argued, verified, and signed." fades in 400ms later  
**And** "Let's run it on your data." appears 600ms after the tagline at large size (40pt equiv)  
**And** "Where should we start?" appears 800ms after the CTA text, slightly smaller

### AC-14-03 — CTA button pulse ✓
**Given** "Where should we start?" is visible  
**When** 300ms have elapsed  
**Then** the "Book a live investigation" button pulses once: scale 1.0 → 1.04 → 1.0 over 400ms  
**And** the button uses `bg-primary text-primary-foreground` and `rounded-md`  
**And** the button does NOT pulse again (one pulse only)

### AC-14-04 — The last word is a question ✓
*Editorial criterion*  
**Given** Scene 14 completes  
**When** all text is visible  
**Then** "Where should we start?" is the final visible text element  
**And** it is phrased as a question, not a statement  
**And** the speaker notes do NOT include "Thank you" as the closing line

### AC-14-05 — Particles settled ✓
**Given** `ParticleField mode="settle"` is running  
**When** inspected at any point after 2s  
**Then** particle velocity has decayed to near-zero oscillation  
**And** the field reads as "calm resolution" not "upward tension" (contrast with Scene 01)

---

## Cross-Cutting Acceptance Criteria

### AC-X-01 — Demo mode completeness (all P0 scenes) ✓
**Given** the demo is opened at `/demo?demo=1&cut=5min`  
**When** navigated through all 6 scenes (01, 04, 06, 10, 12, 14) in order  
**Then** no scene shows an error state, loading spinner, or empty state  
**And** no API call fails or shows a network error in the console

### AC-X-02 — Brand token compliance ✓
**Given** all demo components are built  
**When** their source code is reviewed  
**Then** no hard-coded hex color values appear in any `.tsx` file  
**And** all colors reference Tailwind semantic tokens (`primary`, `success`, `warning`, `danger`, etc.)

### AC-X-03 — Challenger/Defender color identity ✓
**Given** the demo is running  
**When** the Challenger agent or any associated element is visible  
**Then** it uses `danger` (red) styling exclusively  
**And** when the Defender agent or any associated element is visible  
**Then** it uses `success` (emerald) styling exclusively  
**And** neither color appears decoratively in the demo without semantic meaning

### AC-X-04 — Timing integrity (10-minute cut) ✓
*Rehearsal criterion*  
**Given** a presenter reads the full narration at 130–140 wpm with the marked pauses  
**When** the 14-scene run is timed  
**Then** total runtime is 10:00 ±30 seconds

### AC-X-05 — 5-minute cut timing ✓
*Rehearsal criterion*  
**Given** a presenter reads scenes 01, 04, 06, 10, 12, 14 only  
**When** the run is timed  
**Then** total runtime is 5:00 ±20 seconds

### AC-X-06 — Keyboard navigation ✓
**Given** a user opens the demo  
**When** they press the right arrow key  
**Then** the next scene loads  
**And** pressing the left arrow key returns to the previous scene  
**And** pressing Escape exits to `/dashboard`

### AC-X-07 — No console errors ✓
**Given** the full 14-scene demo is run in demo mode  
**When** the browser console is monitored throughout  
**Then** zero unhandled errors or unhandled promise rejections appear  
**And** zero 4xx/5xx network errors appear (all data comes from fixtures in demo mode)
