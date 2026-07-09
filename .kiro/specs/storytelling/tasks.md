# GL Guardian — Demo Storytelling: Implementation Tasks

**Spec version:** 1.0  
**Date:** 2026-07-06  
**Estimated total:** ~13–16 story points (SP) per story point ≈ half-day of focused work

Tasks are ordered by the vertical slice priority: P0 items first (the 5-minute cut), then P1 (full 10-min deck), then P2 (polish and fallbacks).

---

## Epic 0 — Foundation (do first, everything depends on this)

### T-00: Demo route skeleton & demo mode infrastructure
**SP:** 2  
**Priority:** P0  
**Blocking:** All other tasks

**Subtasks:**
- [ ] Create route group `UI/app/(demo)/` with a chromeless layout (`bg-[#0B1220] h-screen w-screen overflow-hidden`, no sidebar/nav)
- [ ] Create `UI/app/(demo)/demo/page.tsx` as the entry point
- [ ] Create `UI/hooks/use-demo-mode.ts` — React context providing `enabled`, `toggle`, and fixture accessors
- [ ] Wire `?demo=1` URL param to activate demo mode on mount
- [ ] Wire `?scene=XX` URL param to jump to a specific scene
- [ ] Wire `?cut=5min` URL param to filter scenes to the 5-min cut
- [ ] Create `UI/data/demo/` directory with index barrel export

**Acceptance:** `http://localhost:3000/demo?demo=1` renders without the app sidebar. `?scene=06` jumps directly to Scene 06.

---

### T-01: Demo fixture data
**SP:** 1  
**Priority:** P0  
**Blocking:** T-06, T-08, T-09, T-12

**Subtasks:**
- [ ] Create `UI/data/demo/demo-case.ts` — `DEMO_CASE: Investigation` (Maelstrom Corp GmbH, TXN-2024-8842, $285,000, high risk, `agent_debate` status)
- [ ] Create `UI/data/demo/demo-debate.ts` — `DEMO_DEBATE: DebateArgument[]` (5 entries: Challenger×2, Defender×2, Adjudicator×1, with scripted confidence values [0.42, 0.61, 0.55, 0.78, 0.83])
- [ ] Create `UI/data/demo/demo-audit-chain.ts` — `DEMO_AUDIT_CHAIN: AuditEvent[]` (12 blocks, `tamperedIndex: 6`)
- [ ] Create `UI/data/demo/demo-evidence.ts` — `DEMO_EVIDENCE: EvidenceSource[]` (4 sources, one `unsupported`)
- [ ] Create `UI/data/demo/index.ts` barrel export
- [ ] Ensure all fixture types match `UI/types/domain.ts` exactly (no type casts)

**Acceptance:** TypeScript compiles with zero errors against all fixture files.

---

### T-02: `DemoShell` scene sequencer
**SP:** 2  
**Priority:** P0  
**Blocking:** All scene tasks

**Subtasks:**
- [ ] Create `UI/features/demo/demo-shell.tsx` with a `scenes: DemoScene[]` array (full 14-scene and 5-min cut versions)
- [ ] Implement keyboard navigation: Right/Space → next, Left → prev, Escape → exit to `/dashboard`, `?` → toggle speaker notes, `5` → jump to 5-min cut Scene 01
- [ ] Scene transition: current scene fades out (200ms opacity), next scene fades in (400ms)
- [ ] Progress indicator: scene number + title shown as a small pill bottom-center (auto-hides after 2s)
- [ ] Speaker notes overlay: floating 20% opacity panel, bottom of screen, shown on `?notes=1` or keyboard `?` toggle
- [ ] `aria-live="polite"` region announces scene changes for screen readers
- [ ] Scene components receive `isActive` prop; only the active scene runs animations

**Acceptance:** Full keyboard navigation works. All 14 scenes can be traversed. Speaker notes are visible in notes mode.

---

## Epic 1 — The 5-Minute Cut (P0)

### T-03: Scene 01 — Cold open (`ParticleField` + `SceneTitle`)
**SP:** 2  
**Priority:** P0  
**Dependencies:** T-00, T-01

**Subtasks:**
- [ ] Create `UI/components/demo/particle-field.tsx`
  - Canvas-based, 2000 particles max, 60fps via `requestAnimationFrame`
  - `mode: 'stream' | 'settle'` — stream = upward drift, settle = calm constellation
  - `highlightRatio: number` (default 0.05) — ratio of blue-lit particles to grey
  - `will-change: transform` on the canvas element
  - `prefers-reduced-motion`: skip animation, show static gradient `bg-[#0B1220]`
  - Cleanup: `cancelAnimationFrame` on unmount
- [ ] Create `UI/components/demo/scene-title.tsx`
  - `title: string`, `subtitle?: string`, `stat?: string` (stat shown bottom-right)
  - Blur-to-focus entrance: `filter: blur(8px) → blur(0)` + `opacity: 0→1` over 1.5s
  - Uses Inter Display equiv: `text-5xl font-bold tracking-tight text-white`
- [ ] Create `UI/features/demo/scene-01-cold-open.tsx` composing the above
  - Title: "EVERY TRANSACTION IS A QUESTION NO ONE HAS TIME TO ASK"
  - Sub: "Last year, your business processed millions of transactions."
  - Stat: "~5% sampled" fades in after 2s

**Acceptance:** Scene 01 renders with upward-drifting particles, blur-to-focus title, and the ~5% stat. Canvas runs at ≥30fps on a modern laptop.

---

### T-04: Scene 04 — Vision reveal (`DayBreakWipe` + logo convergence)
**SP:** 1  
**Priority:** P0  
**Dependencies:** T-00, T-03

**Subtasks:**
- [ ] Add `animate-day-break` keyframe to `UI/app/globals.css` (dark→light wipe, 800ms ease-in-out)
- [ ] Create `UI/components/demo/day-break-wipe.tsx` — wraps children, plays the wipe on `active` prop
- [ ] Create `UI/features/demo/scene-04-vision.tsx`
  - Start: `ParticleField mode="stream"` (dark)
  - Trigger: `DayBreakWipe` transitions to light background (`bg-[#F5F7FB]`)
  - Particles transition to `mode="settle"` and converge to center (CSS `transform: scale(0)` + `translate` to center over 1.5s)
  - Wordmark appears center after particles settle: `opacity: 0→1` with `scale: 0.95→1`
  - Tagline: "Every transaction gets a fair trial" fades in 400ms after wordmark
  - Music cue label (presenter notes): "Music lifts. Hopeful theme."

**Acceptance:** The day-break wipe plays smoothly. The logo appears after particle convergence. The scene correctly bookends to dark in Scene 14.

---

### T-05: Scene 06 — The debate — extended `DebateViewer` (SIGNATURE)
**SP:** 3  
**Priority:** P0  
**Dependencies:** T-00, T-01, T-02

This is the most important scene. Take the most care here.

**Subtasks:**
- [ ] Create `UI/features/demo/scene-06-debate.tsx` wrapping an extended `DebateViewer`
- [ ] Add `demoMode` prop to `DebateView` — when true, loads `DEMO_DEBATE` from fixtures instead of API
- [ ] Implement word-by-word streaming on `DebateMessage` when `streamMessages={true}`:
  - Split `argument.summary` by words
  - Render words with a 60ms interval using `useEffect` + `useState`
  - Transition to `cited` state when complete; animate citation badges in
- [ ] Create `UI/components/demo/verdict-card.tsx`
  - Contains the adjudicator message
  - Entrance: `scale-95 opacity-0 → scale-100 opacity-100`, 400ms, 200ms delay after last argument
  - Gavel icon: rotate 0°→−15°→0° spring animation on entrance
  - Card border: `border-l-4 border-l-primary` + subtle shadow-panel glow
- [ ] Wire `ConfidenceMeter` to scripted sequence: update on each argument completion
  - Values: `[start: 0.5] → [after arg1: 0.42] → [after arg2: 0.61] → [after arg3: 0.55] → [after arg4: 0.78] → [verdict: 0.83]`
  - Existing `ConfidenceMeter` component: add `springConfig?: { stiffness: number; damping: number }` prop
- [ ] Ensure grid layout: `grid-cols-[1fr_auto_1fr]` on desktop, stacked on mobile <768px
- [ ] `aria-live="polite"` on transcript container, `role="log"`, meter `aria-valuenow`
- [ ] Ensure `prefers-reduced-motion`: skip typing animation, show all text immediately

**Acceptance:** Demo mode plays the full scripted debate. The confidence meter visibly tilts as arguments land. The gavel drops on the verdict. The audience CTA "Have you ever seen AI argue with itself?" is present in the speaker notes overlay.

---

### T-06: Scene 10 — Live product walkthrough
**SP:** 2  
**Priority:** P0  
**Dependencies:** T-00, T-01

**Subtasks:**
- [ ] Create `UI/features/demo/scene-10-live-product.tsx`
  - A device mockup frame (laptop/browser) containing an `<iframe>` pointing to `/?demo=1`
    OR a screen-recording `<video>` component with auto-play, loop=false
  - Add a `mode: 'live' | 'recording'` prop — live embeds the real app, recording plays the MP4
- [ ] Implement `?demo=1` seeded flow in the main app:
  - On `/intake?demo=1`: pre-populate with `DEMO_CASE` data, skip the CSV upload dialog
  - On `/dashboard?demo=1`: show `DEMO_CASE` in the investigations list
  - On `/investigations/demo-case-001?demo=1`: pre-populate all tabs with fixture data
  - Pause background WebSocket polling when demo mode is active
- [ ] Create route annotations (breadcrumb chips): "1. Intake → 2. Dashboard → 3. Workspace → 4. Review → 5. Report"
  that light up as the presenter navigates
- [ ] Add a placeholder for `Docs/demo-recording.mp4` — create `Docs/demo-recording.README.md` with recording instructions if MP4 doesn't yet exist
- [ ] Highlight ring: a `ring-2 ring-primary ring-offset-2 rounded-lg` overlay that can be positioned via `data-demo-highlight` attribute and JS

**Acceptance:** `?demo=1` on the intake page shows the Maelstrom Corp case without requiring CSV upload. The workspace shows the debate viewer pre-populated. The presenter can navigate through the full flow without hitting an empty state.

---

### T-07: Scene 12 — Business impact (`ImpactComparison` + `StatCard`)
**SP:** 1  
**Priority:** P0  
**Dependencies:** T-00

**Subtasks:**
- [ ] Create `UI/components/demo/stat-card.tsx`
  - Props: `label`, `before`, `after`, `unit?`, `tone?: 'default'|'success'`
  - Count-up from 0 to `after` value over 1.2s ease-out, triggered by `IntersectionObserver`
  - String values (non-numeric `before`/`after`) cross-dissolve (opacity swap)
  - `prefers-reduced-motion`: show final value immediately
- [ ] Create `UI/features/demo/scene-12-impact.tsx`
  - Two Recharts `PieChart`/`RadialBarChart` side by side: Before (5%, muted grey) and After (100%, success/emerald)
  - Donuts animate: fill from 0 to target value on mount (500ms ease-out)
  - Four `StatCard` instances below:
    1. Coverage: 5% → 100%
    2. Review time: "Hours" → "Minutes" (per auto-cleared case)
    3. Audit decisions: "Sampled" → "Full coverage"
    4. Defensibility: "Rules-based" → "Cited & argued"
  - Before/After labels: Before column in `text-muted-foreground`, After in `text-success-foreground`

**Acceptance:** Both donuts animate. Four stat cards count up. The "After" side is visually dominant.

---

### T-08: Scene 14 — Close / CTA
**SP:** 1  
**Priority:** P0  
**Dependencies:** T-03 (ParticleField)

**Subtasks:**
- [ ] Create `UI/features/demo/scene-14-cta.tsx`
  - Dark navy background, `ParticleField mode="settle"` (calm, sparse constellation)
  - Logo centered (use existing `<Image>` with the SVG logo, white version)
  - Tagline: "Every transaction gets a fair trial — cited, argued, verified, and signed."
  - CTA text: "Let's run it on your data." — large, white, 40pt
  - Question: "Where should we start?" — slightly smaller, muted, appears 800ms after CTA text
  - CTA button "Book a live investigation" — pulses once: `scale-100 → scale-104 → scale-100` over 400ms, 300ms after question appears
  - Contact / URL line below the button (placeholder text, configurable via env/props)

**Acceptance:** The scene bookends Scene 01 (same dark field). The CTA button pulses once. The last text visible is "Where should we start?". The presenter notes read: "Hold on the logo. End."

---

## Epic 2 — Full 10-Minute Deck (P1)

### T-09: Scene 05 — Agent crew (`AgentCrew` React Flow)
**SP:** 2  
**Priority:** P1  
**Dependencies:** T-00

**Subtasks:**
- [ ] Create `UI/components/agents/agent-crew.tsx` using React Flow (already installed)
- [ ] Define `AgentNode` custom node type with icon circle + role caption
- [ ] Implement radial layout (6 satellites at 60° spacing, 320px radius, CaseNode center)
- [ ] Implement sequential edge draw animation (strokeDashoffset, 600ms per edge, 200ms stagger)
- [ ] `activeAgent` prop: highlight node with `ring-2 ring-primary scale-103`
- [ ] Responsive: below 768px, render a `grid-cols-2` card grid instead of React Flow
- [ ] `role="list"` text alternative for screen readers
- [ ] Create `UI/features/demo/scene-05-agent-crew.tsx` wrapping the component

**Acceptance:** All 6 agents appear with correct icons and colors. Edges draw sequentially. The Challenger node is red, Defender is emerald. Mobile renders the card grid.

---

### T-10: Scene 07 — Evidence & citations (`EvidenceFile`)
**SP:** 1  
**Priority:** P1  
**Dependencies:** T-00, T-01

**Subtasks:**
- [ ] Create `UI/components/demo/evidence-file.tsx`
  - Left column: 4 claims (plain text, 14pt)
  - Right column: source chips (Policy KB, FX Rate API, Vendor Registry, Contract Archive) with source-type icons
  - SVG connector lines drawn between each claim→source (strokeDashoffset animation, 400ms per line, 100ms stagger)
  - One claim pre-marked `unsupported`: shakes (translate-x 4px, 3 cycles, 300ms) then greys out with red strike-through + "Verifier rejected" badge
- [ ] Create `UI/features/demo/scene-07-evidence.tsx`

**Acceptance:** Citation threads draw claim→source. The rejected FX claim shakes and is struck through. The presenter narration note "Like that one. Unsupported — struck from the record." is in speaker notes.

---

### T-11: Scene 08 — Confidence gate (`ConfidenceGate`)
**SP:** 1  
**Priority:** P1  
**Dependencies:** T-00

**Subtasks:**
- [ ] Create `UI/components/shared/confidence-gate.tsx`
  - SVG branching path with three lanes
  - `confidence` prop clamped to [0,1] internally (fixes open audit issue)
  - Token (`<circle>`) follows `offset-path` to correct lane over 900ms
  - Active lane pulses on token arrival (ring animation)
  - Visible legend: three color+label pairs (not color-only)
- [ ] Create `UI/features/demo/scene-08-confidence-gate.tsx`
  - Uses `confidence={0.83}` from the demo case (routes to "Human review" lane — amber)
  - Narrator note: "You spend your judgment where judgment matters."

**Acceptance:** The token routes to the amber lane for confidence=0.83. The legend shows text labels with colors. An aria-live region announces the routing result.

---

### T-12: Scene 09 — Audit chain (`AuditChain`)
**SP:** 1  
**Priority:** P1  
**Dependencies:** T-00, T-01

**Subtasks:**
- [ ] Create `UI/components/audit/audit-chain.tsx`
  - Vertical block list with 12px connectors
  - Each block: event-type icon, hash (truncated 8 chars), prev-hash ref, timestamp, actor
  - Blocks animate in with 300ms drop + 120ms stagger
  - `tamperedIndex` prop: that block gets `border-danger bg-danger-soft`, connector becomes dashed red with `TriangleAlert` icon
  - `aria-live="assertive"` announces tamper state
  - Windowed render for >50 blocks (simple slice, no library needed)
- [ ] Create `UI/features/demo/scene-09-audit-chain.tsx`
  - Uses `DEMO_AUDIT_CHAIN`, `tamperedIndex={6}` initially off, then toggled by a "tamper demo" button
  - Presenter can press `T` key to trigger the tamper visualization live on stage

**Acceptance:** Chain renders with 12 blocks. Pressing `T` breaks block 6 and shows the dashed red connector. `aria-live` fires. Blocks animate in on scene entry.

---

### T-13: Scenes 02, 03, 11, 13 — Remaining scenes (layout only)
**SP:** 2  
**Priority:** P1  
**Dependencies:** T-00

These scenes are visual/static and don't require new interactive components. Each is implemented as a styled layout using existing components.

**Subtasks:**
- [ ] Scene 02: Three stacked pain-cards (clock, bell, iceberg) sliding in from the left, 120ms stagger. Uses `Card` component with custom icons and copy.
- [ ] Scene 03: Three stat callouts counting up (auditor hours, % unexamined, $ exposure). Reuse `StatCard`. Light red for the exposure number.
- [ ] Scene 11: Horizontal pipeline conveyor: Intake → Evidence → Debate → Verify → Gate → Report → Audit. Infra icons pulse below each stage. Uses a simple flex row with animated connecting arrows.
- [ ] Scene 13: Horizon timeline with 5 milestone nodes (Copilot, Real-time, Multi-model, Integrations, Marketplace). Sequential light-up animation toward a vanishing point. A `z-index` gradient simulates perspective.

**Acceptance:** All four scenes render without errors, display correct content, and have speaker notes visible in notes mode.

---

## Epic 3 — Polish & Production Readiness (P2)

### T-14: Speaker notes overlay
**SP:** 1  
**Priority:** P2  
**Dependencies:** T-02

**Subtasks:**
- [ ] Create `UI/components/demo/speaker-notes.tsx`
  - Semi-transparent panel, bottom of screen, max 25% height
  - Shows the narration text for the current scene
  - `?notes=1` or keyboard `?` toggles visibility
  - `opacity-20` when visible (doesn't block the demo visual)
  - Each scene component exports a `speakerNotes: string` constant

**Acceptance:** Notes overlay shows the correct narration beat for each scene. Toggle with `?` works.

---

### T-15: Recorded fallback (`demo-recording.md`)
**SP:** 0.5  
**Priority:** P2  
**Dependencies:** T-06

**Subtasks:**
- [ ] Create `Docs/demo-recording.README.md` with step-by-step instructions for recording the Scene 10 walkthrough
- [ ] Create the `video` element in Scene 10 with `mode="recording"` support, pointing to `/demo/recording.mp4`
- [ ] Add `recording.mp4` to `.gitignore` (binary file) but document its expected location

**Acceptance:** When `mode="recording"`, the scene renders a `<video>` player with the MP4. The recording README gives complete instructions for re-capturing.

---

### T-16: Accessibility audit pass
**SP:** 1  
**Priority:** P2  
**Dependencies:** All scene tasks

**Subtasks:**
- [ ] Run axe-core against all demo scenes in demo mode
- [ ] Verify WCAG 2.1 AA contrast on all text (check dark/light modes)
- [ ] Verify all interactive elements are keyboard-navigable
- [ ] Verify `prefers-reduced-motion` disables all motion-only animations
- [ ] Verify color is never the sole differentiator (debate sides, gate lanes, claim status)
- [ ] Add `aria-label` to all icon-only buttons
- [ ] Add skip-to-main-content link on the demo layout

**Acceptance:** Zero critical or serious axe-core violations on any scene. All motion has a static fallback.

---

### T-17: Performance verification
**SP:** 0.5  
**Priority:** P2  
**Dependencies:** All scene tasks

**Subtasks:**
- [ ] Verify FCP ≤1.5s for the demo route (Lighthouse in CI mode)
- [ ] Verify ParticleField canvas renders at ≥30fps on a mid-range laptop (Chrome DevTools)
- [ ] Verify React Flow (Scene 05) renders in ≤200ms for 6 nodes
- [ ] Add `loading="lazy"` to all non-critical images
- [ ] Ensure demo mode fixtures are tree-shaken from the production bundle (lazy import or `process.env.NODE_ENV` guard)

**Acceptance:** Lighthouse performance score ≥80 for the demo route. Particle field doesn't drop below 30fps.

---

## Dependency Graph

```
T-00 (foundation)
  ├── T-01 (fixtures)     ──→ T-05, T-06, T-08, T-09
  ├── T-02 (shell)        ──→ T-14
  ├── T-03 (particles)    ──→ T-04, T-08 (Scene 14)
  ├── T-04 (vision)
  ├── T-05 (debate) ← T-01, T-03
  ├── T-06 (live product) ← T-01
  ├── T-07 (impact)
  └── T-08 (CTA) ← T-03
  
T-09 (agent crew)   ← T-00
T-10 (evidence)     ← T-00, T-01
T-11 (gate)         ← T-00
T-12 (chain)        ← T-00, T-01
T-13 (remaining)    ← T-00

T-14 (notes)        ← T-02
T-15 (recording)    ← T-06
T-16 (a11y)         ← all scenes
T-17 (perf)         ← all scenes
```

---

## Story Point Summary

| Epic | Tasks | SP |
|------|-------|----|
| 0 — Foundation | T-00, T-01, T-02 | 5 |
| 1 — 5-min cut (P0) | T-03 through T-08 | 10 |
| 2 — Full deck (P1) | T-09 through T-13 | 7 |
| 3 — Polish (P2) | T-14 through T-17 | 3 |
| **Total** | **17 tasks** | **~25 SP** |

The 5-minute cut (Epic 0 + Epic 1) is the **minimum shippable demo**: 15 SP, approximately 7–8 focused work-days.
