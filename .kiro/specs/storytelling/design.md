# Skeptic Engine — Demo Storytelling: Design

**Spec version:** 1.0  
**Date:** 2026-07-06  
**Companion files:** `requirements.md`, `tasks.md`, `scene-acceptance-criteria.md`, `vertical-slice-plan.md`

---

## 1. Architecture Overview

The demo storytelling layer is a **presentation route** within the existing Next.js 15 App Router application. It reuses all existing design tokens, components, and data services — the goal is zero new design debt, only composition.

```
UI/
├── app/(app)/
│   └── demo/                        ← NEW: demo presentation route
│       ├── page.tsx                 ← Scene sequencer shell
│       ├── layout.tsx               ← Chromeless layout (no sidebar/nav)
│       └── [scene]/
│           └── page.tsx             ← Optional direct scene link
├── features/
│   └── demo/                        ← NEW: demo feature module
│       ├── demo-shell.tsx           ← Scene carousel / controller
│       ├── scene-01-cold-open.tsx
│       ├── scene-04-vision.tsx
│       ├── scene-05-agent-crew.tsx
│       ├── scene-06-debate.tsx
│       ├── scene-07-evidence.tsx
│       ├── scene-08-confidence-gate.tsx
│       ├── scene-09-audit-chain.tsx
│       ├── scene-10-live-product.tsx
│       ├── scene-12-impact.tsx
│       └── scene-14-cta.tsx
├── components/
│   ├── demo/                        ← NEW: demo-specific primitives
│   │   ├── particle-field.tsx       ← Scene 01/14 shared particle motif
│   │   ├── day-break-wipe.tsx       ← Scene 03→04 signature transition
│   │   ├── stat-card.tsx            ← Reusable count-up stat card
│   │   └── scene-title.tsx          ← Blur-to-focus title entrance
│   ├── debate/
│   │   └── debate-message.tsx       ← EXISTS — extend for streaming/typed state
│   ├── agents/
│   │   └── agent-crew.tsx           ← NEW: React Flow crew diagram
│   └── shared/
│       ├── confidence-meter.tsx     ← EXISTS — extend with spring animation
│       └── confidence-gate.tsx      ← NEW: branching 3-lane gate
├── data/
│   └── demo/                        ← NEW: typed fixture data
│       ├── demo-case.ts             ← Seeded case: Maelstrom Corp / TXN-2024-8842
│       ├── demo-debate.ts           ← Pre-scripted Challenger/Defender exchange
│       ├── demo-audit-chain.ts      ← 12-block chain with one tampered block
│       └── demo-evidence.ts         ← Evidence file with one unsupported claim
└── hooks/
    └── use-demo-mode.ts             ← NEW: demo mode context + fixture switching
```

---

## 2. Scene Architecture

### 2.1 Scene sequencer (`demo-shell.tsx`)

The shell manages scene state and keyboard/click navigation. It is the single source of truth for which scene is visible.

```typescript
type DemoScene = {
  id: string;          // e.g. "01", "06"
  name: string;        // display name
  duration: number;    // seconds
  inCut: '10min' | '5min' | 'both';
  component: React.ComponentType<SceneProps>;
};

type SceneProps = {
  demoMode: boolean;       // use fixtures, not live API
  isActive: boolean;       // controls whether animations run
  onComplete?: () => void; // signal scene done to shell
};
```

Navigation:
- Right arrow / click → next scene
- Left arrow → previous scene
- `Escape` → exit to normal app
- `?` → toggle speaker notes overlay
- `5` → jump to 5-min cut start

### 2.2 Scene lifecycle

Each scene component follows three phases:

1. **Enter** (`isActive` becomes `true`): hero animation plays, narration cue fires.
2. **Idle**: scene holds, presenter speaks/demonstrates.
3. **Exit** (`isActive` becomes `false`): quick fade-out, next scene enters.

---

## 3. Component Design

### 3.1 `ParticleField` (Scenes 01, 14)

A Canvas-based particle emitter to avoid layout thrash. 

```typescript
type ParticleFieldProps = {
  mode: 'stream' | 'settle'; // stream = upward drift; settle = calm constellation
  highlightRatio?: number;   // default 0.05 (5% lit blue, rest grey)
  className?: string;
};
```

**Implementation strategy:** `requestAnimationFrame` loop on a `<canvas>` element. Each particle is a 2×4px rectangle. On `mode="stream"` particles drift upward at 0.4–1.2px/frame with random lateral drift. On `mode="settle"` velocity decays to near-zero with gentle oscillation.

Performance constraint: max 2000 particles at 60fps on a modern laptop. Use `devicePixelRatio` correction.

### 3.2 `DayBreakWipe` (Scene 03→04 transition)

A named CSS animation applied to the scene container. Not a new component — a Tailwind utility class:

```css
@keyframes day-break-wipe {
  0%   { background: #0B1220; clip-path: inset(0 100% 0 0); }
  100% { background: #F5F7FB; clip-path: inset(0 0% 0 0); }
}
.animate-day-break { animation: day-break-wipe 800ms ease-in-out forwards; }
```

Reuse a 400ms soft version for internal scene transitions.

### 3.3 `AgentCrew` — React Flow crew diagram (Scene 05)

```typescript
type AgentCrewProps = {
  activeAgent?: AgentRole | null;
  animateEdges?: boolean;   // draw edges sequentially on mount
  demoMode?: boolean;
};
```

**Node layout:** Radial. Center: `CaseNode` (blue). Satellites at 320px radius, 60° spacing:
1. Supervisor (top, ~90°)
2. Evidence (top-right, ~30°)
3. Challenger (bottom-right, ~330°)
4. Defender (bottom-left, ~270°)
5. Adjudicator (bottom, ~210°)
6. Verifier (top-left, ~150°)

**AgentNode component:**

```typescript
type AgentNodeData = {
  role: AgentRole;
  icon: LucideIcon;
  colorScheme: 'primary' | 'danger' | 'success';
  state: 'default' | 'active' | 'running' | 'done' | 'failed';
  caption: string;
};
```

CSS: `w-[120px] rounded-lg border bg-card shadow-card p-3 flex flex-col items-center gap-2`

Icon circle: `h-10 w-10 rounded-full flex items-center justify-center` + semantic soft-color background.

**Edge animation:** `strokeDasharray` = total path length. Animate `strokeDashoffset` from path-length to 0 over 600ms with `animationDelay: index * 200ms`.

**Responsive fallback (<768px):** Replace React Flow with a `grid grid-cols-2 gap-3` of plain agent cards. Same data, no SVG.

### 3.4 `DebateViewer` — enhanced for demo (Scene 06)

Extends the existing `DebateView` feature component. New additions:

```typescript
type DebateViewerProps = {
  caseId?: string;
  demoMode?: boolean;         // use demo-debate.ts fixtures
  streamMessages?: boolean;   // enable character-by-character typing
  showNarrationCues?: boolean; // presenter mode
};
```

**Message streaming:** Each `DebateMessage` in demo mode renders characters progressively using a `useEffect` with a 30ms character interval. Once fully rendered, state transitions to `cited` and citation badges animate in.

**ConfidenceMeter integration:** The meter is already used in `DebateView`. For demo mode, wire it to a sequence of pre-scripted values that update as each argument completes: `[0.42, 0.61, 0.55, 0.78, 0.83]` (Challenger suppresses, Defender recovers, Adjudicator settles at 0.83).

**VerdictCard:** Extend the existing adjudicator card with:
- `scale-95 opacity-0` → `scale-100 opacity-100` entrance (400ms, delay 200ms after last argument)
- A `Gavel` icon animation: rotate 0° → −15° → 0° (the "gavel drop" effect, spring physics)
- A ripple `::after` pseudo-element on the card border

**Layout tokens:**
```
grid-cols-[1fr_auto_1fr]  // desktop
gap-6                     // column gutter
space-y-4                 // message spacing within column
min-w-[280px]             // meter column
```

### 3.5 `ConfidenceGate` — branching SVG gate (Scene 08)

```typescript
type ConfidenceGateProps = {
  confidence: number;      // [0, 1] — clamped internally
  animate?: boolean;       // play the token routing animation
  showLegend?: boolean;    // default true
};
```

**SVG path structure:**

```
Entry point (left)
    │
    ▼
  [GATE]
  /  |  \
 /   |   \
[≥0.90] [0.70-0.90] [<0.70]
Auto-clear Human-review Escalate
(success)  (warning)   (danger)
```

The token (`<circle r="8">`) follows an `offset-path` CSS animation. The path has three `<polyline>` branches. On mount with `animate={true}`, the token travels to the correct branch based on `confidence`.

**Lane colors:** Use Tailwind semantic variables directly:
- `stroke-success` for ≥0.90
- `stroke-warning` for 0.70–0.90
- `stroke-danger` for <0.70

### 3.6 `AuditChain` (Scene 09)

```typescript
type AuditChainProps = {
  events: AuditEvent[];
  tamperedIndex?: number;  // demo: which block to visually break
  maxVisible?: number;     // virtualization window
};
```

**Block layout:**

```
┌────────────────────────────────────────┐
│ [event-type icon]  EventType           │
│ actor · timestamp                      │
│ hash: 3f7a...e2b1                      │
│ prev: 9c44...a017                      │
└────────────────────────────────────────┘
         │   (12px connector)
┌────────────────────────────────────────┐
│ ...                                    │
```

**Tampered state:** Block at `tamperedIndex` gets `border-danger bg-danger-soft`. The connector between `tamperedIndex - 1` and `tamperedIndex` renders as a dashed red line with a `TriangleAlert` icon. An `aria-live="assertive"` region announces "Chain integrity broken at record N".

**Virtualization:** Use a simple windowed render (render ±5 around the viewport center) for chains >50 blocks. A full virtualization library (like `@tanstack/virtual`) is overkill for the demo context.

### 3.7 `StatCard` — count-up on intersection (Scene 12)

```typescript
type StatCardProps = {
  label: string;
  before: string | number;
  after: string | number;
  unit?: string;
  tone?: 'default' | 'success';
};
```

Uses `IntersectionObserver` to trigger the count-up animation when the card enters the viewport. The count-up runs over 1.2s with ease-out. String values (e.g., "Hours → Minutes") cross-dissolve rather than count.

---

## 4. Demo Mode (`use-demo-mode.ts`)

A React context that provides fixture data and suppresses live API calls during the demo.

```typescript
type DemoModeContext = {
  enabled: boolean;
  demoCase: Investigation;
  demoDebate: DebateArgument[];
  demoAuditChain: AuditEvent[];
  demoEvidence: EvidenceSource[];
  toggle: () => void;
};
```

**Activation:**
1. URL parameter: `?demo=1` sets demo mode for the session
2. Keyboard shortcut (dev only): `Ctrl+Shift+D` toggles
3. The demo route (`/demo`) always runs in demo mode

**Safety:** Demo mode must never activate in production environments unless explicitly triggered. Add a `process.env.NODE_ENV !== 'production'` guard on the keyboard toggle.

---

## 5. Brand & Design Token Map

All components must use the following token mapping. No hex values in TSX files.

| Brand color | Tailwind token | CSS variable | Semantic role |
|-------------|---------------|--------------|---------------|
| Skeptic Blue #2563EB | `primary` | `--primary` | Brand, actions, data flow |
| Keynote Navy #0B1220 | `background` (dark mode) | `--background` | Dark scenes |
| Defender Emerald #10B981 | `success` | `--success` | Defender, cleared, verified |
| Challenger Red #EF4444 | `danger` | `--danger` | Challenger, risk, escalate |
| Review Amber #F59E0B | `warning` | `--warning` | Human review, in-progress |
| Body Ink #151A2D | `foreground` | `--foreground` | Body text |
| Muted Slate #64748B | `muted-foreground` | `--muted-foreground` | Captions, secondary |
| Ice #EAF1FB | `primary-soft` | `--primary-soft` | Chips, soft fills |
| Light Surface #F5F7FB | `background` (light) | `--background` | Light scenes |
| Border #D8DFEC | `border` | `--border` | Hairlines, dividers |

**Shadow tokens:**
- `shadow-card` → `0 1px 2px rgba(15,23,42,0.06), 0 10px 24px rgba(15,23,42,0.04)`
- `shadow-panel` → `0 16px 40px rgba(15,23,42,0.12)`

**Typography:**
- `font-sans` → Inter (UI text, narration, labels)
- `font-mono` → JetBrains Mono (confidence scores, hashes, thresholds, data)

---

## 6. Animation Design System

### 6.1 Easing tokens

```css
--ease-out-expo: cubic-bezier(0.16, 1, 0.3, 1);   /* entrances */
--ease-in-out:   cubic-bezier(0.4, 0, 0.2, 1);     /* meters, camera */
```

### 6.2 Duration tokens

| Name | Value | Use |
|------|-------|-----|
| `duration-micro` | 200ms | Hover, chips, focus |
| `duration-base` | 400ms | Card reveals, slide-ins |
| `duration-hero` | 800ms | Scene titles, logo |
| `duration-slow` | 1200ms | Stat count-ups, particle convergence |
| `duration-max` | 1500ms | Logo assembly (hard cap) |

### 6.3 Per-scene signature move summary

| Scene | Signature move | Component/CSS |
|-------|---------------|---------------|
| 01 | Upward particle drift + blur-to-focus title | `ParticleField` + `SceneTitle` |
| 04 | Particle convergence into logo + day-break wipe | `ParticleField(settle)` + `.animate-day-break` |
| 05 | Sequential edge draw on React Flow nodes | `AgentCrew` animated edges |
| 06 | Typed arguments + spring confidence needle + gavel ripple | `DebateViewer` extended |
| 07 | Citation thread draw + rejected claim shake | `EvidenceFile` new component |
| 08 | Token routing down SVG path | `ConfidenceGate` |
| 09 | Chain blocks drop + tamper crack | `AuditChain` |
| 10 | Cross-dissolve screen montage + highlight ring | `LiveProductDemo` |
| 12 | Donut fill + stat card count-up | `ImpactComparison` + `StatCard` |
| 14 | Particles settle + CTA pulse | `ParticleField(settle)` |

### 6.4 `prefers-reduced-motion` fallback

Wrap all motion in a `useReducedMotion()` hook. When `true`:
- Skip `y` translate animations; use opacity fade only
- Skip character-by-character typing; show final text immediately
- Skip particle field entirely; show a static dark gradient
- Skip stat count-ups; show final values immediately

---

## 7. Demo Fixture Data Design

### 7.1 Demo case — `demo-case.ts`

```typescript
// Transaction: Maelstrom Corp GmbH — International consultant payment
// This case is designed to be genuinely ambiguous:
// - $285,000 wire to an overseas entity
// - Vendor is real in the registry but was recently added
// - FX rate claim is slightly off
// - Legitimate explanation exists (software licensing)
// Purpose: shows the debate being genuinely contested, not trivially one-sided
export const DEMO_CASE: Investigation = {
  id: 'demo-case-001',
  transactionId: 'TXN-2024-8842',
  vendor: 'Maelstrom Corp GmbH',
  category: 'Consulting & Professional Services',
  amount: 285000,
  confidence: 0.83,
  risk: 'high',
  flags: ['large_wire', 'new_vendor_90d', 'fx_variance', 'single_approver'],
  status: 'agent_debate',
  // ...
};
```

### 7.2 Demo debate — `demo-debate.ts`

Pre-scripted two-round exchange (4 arguments + 1 adjudicator verdict):

| # | Side | Title | Key claim | Confidence after |
|---|------|-------|-----------|-----------------|
| 1 | Challenger | Large wire to unverified entity | $285k exceeds materiality; vendor added 87 days ago | 0.42 |
| 2 | Defender | Vendor verified in registry; contract exists | Licensing agreement on file; FX delta within 2% | 0.61 |
| 3 | Challenger | FX rate claim unsupported | Verifier flagged one FX citation as ungrounded | 0.55 |
| 4 | Defender | Contract terms justify payment timing | Payment timing matches contract milestone clause 7.3 | 0.78 |
| 5 | Adjudicator | Cleared with conditions | Vendor legitimate; FX claim revised; recommend monitoring for 90d | 0.83 |

### 7.3 Demo audit chain — `demo-audit-chain.ts`

12-block chain. Block 7 is the `tamperedIndex` for the demo. Blocks have realistic hash values (not random — pre-computed so the demo always shows the same chain).

### 7.4 Demo evidence — `demo-evidence.ts`

4 evidence sources: Policy KB, FX Rate API, Vendor Registry, Contract Archive. One claim (the FX rate claim from round 3) is pre-marked `unsupported` and triggers the Verifier rejection animation.

---

## 8. Route Design

### 8.1 Demo presentation route

`/demo` — full-screen, chromeless (no sidebar, no nav, no top bar).

Query params:
- `?scene=06` — jump to specific scene
- `?cut=5min` — 5-minute cut (scenes 01, 04, 06, 10, 12, 14 only)
- `?notes=1` — show speaker notes overlay
- `?demo=1` — (implicit for this route) demo mode

### 8.2 Layout override

The `(app)` layout has a sidebar. The demo needs its own layout:

```typescript
// UI/app/(demo)/layout.tsx
export default function DemoLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="h-screen w-screen overflow-hidden bg-[#0B1220]">
      {children}
    </div>
  );
}
```

This requires a new route group `(demo)` parallel to `(app)`.

---

## 9. Integration with Existing Components

### 9.1 Components reused without modification

| Component | Location | Used in scene |
|-----------|----------|---------------|
| `DebateMessage` | `components/debate/debate-message.tsx` | 06 |
| `ConfidenceMeter` | `components/shared/confidence-meter.tsx` | 06, 08 |
| `Badge` | `components/ui/badge.tsx` | All |
| `Card`, `CardContent` | `components/ui/card.tsx` | All |
| Recharts components | (via features/analytics) | 12 |

### 9.2 Components extended

| Component | Extension | Scene |
|-----------|-----------|-------|
| `DebateView` | Add `demoMode` + `streamMessages` props | 06 |
| `ConfidenceMeter` | Add spring physics option + `aria-*` attributes | 06, 08 |
| `AuditEvent` display | Wrap in `AuditChain` with tamper demo | 09 |

### 9.3 Components created new

| Component | Scene |
|-----------|-------|
| `ParticleField` | 01, 14 |
| `SceneTitle` | 01, 04 |
| `AgentCrew` (React Flow) | 05 |
| `VerdictCard` (gavel animation) | 06 |
| `EvidenceFile` (citation threads) | 07 |
| `ConfidenceGate` (SVG routing) | 08 |
| `AuditChain` (hash blocks) | 09 |
| `StatCard` (count-up) | 12 |
| `ImpactComparison` (donut pair) | 12 |
| `DemoShell` (scene sequencer) | All |

---

## 10. Open Design Decisions

| # | Decision | Options | Recommended | Rationale |
|---|----------|---------|-------------|-----------|
| D1 | Particle field implementation | CSS, Canvas, WebGL | Canvas | CSS can't handle 2000 particles without jank; WebGL is overkill for 2D embers |
| D2 | Scene 06 message streaming | Per-character interval, word-by-word, full text on demand | Word-by-word | Character-by-character feels slow on longer arguments; word-by-word feels "live" |
| D3 | React Flow in 5-min cut | Full graph or static illustration | Full graph (Scene 05 is not in 5-min cut; Scene 06 header shows the two debaters) | The graph only appears in Scene 05, which is skipped in the 5-min cut |
| D4 | Demo route auth | Protected (requires login) or public | Public for demo route | Demo is shown to prospects who haven't logged in; add a `DEMO_ACCESS_TOKEN` env guard if needed |
| D5 | Speaker notes overlay | Separate panel, floating overlay | Floating bottom overlay 20% opacity, `notes=1` only | Doesn't block the demo; can be closed; keyboard `?` toggle |
