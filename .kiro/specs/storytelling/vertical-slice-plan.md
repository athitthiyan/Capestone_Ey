# GL Guardian — Vertical Slice Implementation Plan

**Spec version:** 1.0  
**Date:** 2026-07-06  
**Scope:** Scenes 01, 04, 06, 10, 14 (the 5-minute cut, minus Scene 12 which is pure layout)  
**Goal:** A shippable, end-to-end demo in ~7 focused work-days

> A vertical slice cuts through every layer — route, component, data, animation, accessibility — for a small number of scenes. Ship this slice first. The remaining scenes can be added scene-by-scene without blocking the demo.

---

## Slice Overview

| Scene | Name | New components | Existing components reused | Est. hours |
|-------|------|---------------|---------------------------|------------|
| Foundation | Route + demo mode | `DemoShell`, `use-demo-mode` | — | 4h |
| Fixtures | Demo data | All fixture files | `Investigation`, `DebateArgument`, `AuditEvent` types | 2h |
| 01 | Cold open | `ParticleField`, `SceneTitle` | — | 4h |
| 04 | Vision | `DayBreakWipe` | `ParticleField` (reused) | 2h |
| 06 | The debate | `VerdictCard` | `DebateView`, `DebateMessage`, `ConfidenceMeter` | 6h |
| 10 | Live product | `LiveProductDemo` | All workspace/intake/dashboard components | 4h |
| 14 | CTA | `scene-14-cta` | `ParticleField` (reused) | 2h |
| **Total** | | | | **~24h** |

---

## Day-by-Day Plan

| Day | Focus | Deliverable |
|-----|-------|-------------|
| 1 | Foundation: route, layout, shell, demo mode, fixtures | `/demo` route works, keyboard nav, fixture data typed |
| 2 | Scene 01 + ParticleField | Cold open plays with particles + blur-to-focus title |
| 3 | Scene 04 + Scene 14 | Day-break wipe + logo; CTA with settled particles |
| 4 | Scene 06 — DebateViewer extended | Scripted debate streams, meter reacts, gavel drops |
| 5 | Scene 06 — polish + a11y | aria-live, reduced-motion, mobile stack, error state |
| 6 | Scene 10 — demo mode seeded flow | `?demo=1` seeds the case end-to-end in the real app |
| 7 | Integration + rehearsal run | Full 5-min cut runs without errors; speaker notes visible |

---

## Step 1 — Foundation (Day 1)

### 1.1 New route group `(demo)`

Create a parallel route group to `(app)` so the demo gets a chromeless layout:

```
UI/app/(demo)/
  layout.tsx          ← chromeless, full-screen, dark bg
  demo/
    page.tsx          ← entry; reads ?scene, ?cut, ?notes URL params
```

**`UI/app/(demo)/layout.tsx`:**
```tsx
export default function DemoLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="h-screen w-screen overflow-hidden bg-[#0B1220] font-sans antialiased">
        {children}
      </body>
    </html>
  );
}
```

> Note: Next.js App Router allows multiple `layout.tsx` root segments. The `(demo)` group shares the root `app/layout.tsx` metadata but overrides the shell. If the root layout includes `<html>/<body>`, nest the override differently — use a `div` wrapper instead and strip the sidebar via CSS.

### 1.2 `use-demo-mode.ts`

```tsx
// UI/hooks/use-demo-mode.ts
"use client";
import { createContext, useContext, useState, useEffect } from "react";
import type { Investigation, DebateArgument, AuditEvent, EvidenceSource } from "@/types/domain";
import {
  DEMO_CASE, DEMO_DEBATE, DEMO_AUDIT_CHAIN, DEMO_EVIDENCE
} from "@/data/demo";

type DemoModeContext = {
  enabled: boolean;
  demoCase: Investigation;
  demoDebate: DebateArgument[];
  demoAuditChain: AuditEvent[];
  demoEvidence: EvidenceSource[];
};

const Ctx = createContext<DemoModeContext | null>(null);

export function DemoModeProvider({
  children,
  initialEnabled = false,
}: {
  children: React.ReactNode;
  initialEnabled?: boolean;
}) {
  const [enabled] = useState(initialEnabled);
  return (
    <Ctx.Provider value={{
      enabled,
      demoCase: DEMO_CASE,
      demoDebate: DEMO_DEBATE,
      demoAuditChain: DEMO_AUDIT_CHAIN,
      demoEvidence: DEMO_EVIDENCE,
    }}>
      {children}
    </Ctx.Provider>
  );
}

export function useDemoMode() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useDemoMode must be used inside DemoModeProvider");
  return ctx;
}
```

### 1.3 `DemoShell` scene sequencer

```tsx
// UI/features/demo/demo-shell.tsx
"use client";
import { useState, useEffect, useCallback } from "react";
import type { DemoScene } from "./scene-registry";

type DemoShellProps = {
  scenes: DemoScene[];
  initialSceneId?: string;
  notesMode?: boolean;
};

export function DemoShell({ scenes, initialSceneId, notesMode = false }: DemoShellProps) {
  const [idx, setIdx] = useState(() => {
    const i = scenes.findIndex(s => s.id === initialSceneId);
    return i >= 0 ? i : 0;
  });
  const [showNotes, setShowNotes] = useState(notesMode);

  const next = useCallback(() => setIdx(i => Math.min(i + 1, scenes.length - 1)), [scenes]);
  const prev = useCallback(() => setIdx(i => Math.max(i - 1, 0)), []);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "ArrowRight" || e.key === " ") next();
      if (e.key === "ArrowLeft") prev();
      if (e.key === "Escape") window.location.href = "/dashboard";
      if (e.key === "?") setShowNotes(n => !n);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [next, prev]);

  const current = scenes[idx];
  const SceneComponent = current.component;

  return (
    <div className="relative h-screen w-screen overflow-hidden" onClick={next}>
      {/* aria-live for screen readers */}
      <div aria-live="polite" className="sr-only">
        Scene {current.id}: {current.name}
      </div>

      <SceneComponent isActive={true} demoMode={true} />

      {/* Scene indicator pill */}
      <div className="pointer-events-none absolute bottom-6 left-1/2 -translate-x-1/2
                      rounded-full bg-white/10 px-3 py-1 text-xs text-white/60 font-mono">
        {current.id} / {scenes.length} — {current.name}
      </div>

      {/* Speaker notes overlay */}
      {showNotes && current.speakerNotes && (
        <div className="pointer-events-none absolute bottom-0 left-0 right-0 max-h-[25%]
                        overflow-y-auto bg-black/80 p-4 text-sm text-white/70 leading-6">
          {current.speakerNotes}
        </div>
      )}
    </div>
  );
}
```

### 1.4 Fixture data files

**`UI/data/demo/demo-case.ts`** (abbreviated — full fixture implements all `Investigation` fields):
```ts
import type { Investigation } from "@/types/domain";

export const DEMO_CASE: Investigation = {
  id: "demo-case-001",
  transactionId: "TXN-2024-8842",
  vendor: "Maelstrom Corp GmbH",
  category: "Consulting & Professional Services",
  amount: 285000,
  confidence: 0.83,
  risk: "high",
  flags: ["large_wire", "new_vendor_90d", "fx_variance", "single_approver"],
  status: "agent_debate",
  owner: "demo-user@example.com",
  reviewer: undefined,
  postedAt: "2024-11-15T09:00:00Z",
  dueAt: "2024-11-22T17:00:00Z",
  materiality: 250000,
  description:
    "International wire payment to a consulting entity registered 87 days prior to payment. " +
    "Payment exceeds materiality threshold. Single approver. FX rate deviation flagged.",
};
```

---

## Step 2 — Scene 01: Cold open (Day 2)

### 2.1 `ParticleField` component

**File:** `UI/components/demo/particle-field.tsx`

Key implementation details:
- Canvas-based (not CSS), to handle 2000 particles without layout thrash.
- Two modes: `stream` (particles drift upward) and `settle` (velocity decays to oscillation).
- `highlightRatio` controls the fraction lit in `primary` blue vs. grey.
- Honors `prefers-reduced-motion` by rendering a static gradient.

```tsx
"use client";
import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";

type ParticleFieldProps = {
  mode?: "stream" | "settle";
  highlightRatio?: number;
  className?: string;
};

type Particle = {
  x: number; y: number;
  vx: number; vy: number;
  highlighted: boolean;
  alpha: number;
};

function initParticles(count: number, w: number, h: number, ratio: number): Particle[] {
  return Array.from({ length: count }, (_, i) => ({
    x: Math.random() * w,
    y: Math.random() * h,
    vx: (Math.random() - 0.5) * 0.3,
    vy: -(0.4 + Math.random() * 0.8),
    highlighted: i / count < ratio,
    alpha: 0.3 + Math.random() * 0.7,
  }));
}

export function ParticleField({
  mode = "stream",
  highlightRatio = 0.05,
  className,
}: ParticleFieldProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const reducedMotion =
    typeof window !== "undefined"
      ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
      : false;

  useEffect(() => {
    if (reducedMotion) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const W = canvas.offsetWidth;
    const H = canvas.offsetHeight;
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    ctx.scale(dpr, dpr);

    const particles = initParticles(2000, W, H, highlightRatio);
    let rafId: number;

    function draw() {
      if (!ctx) return;
      ctx.clearRect(0, 0, W, H);
      for (const p of particles) {
        ctx.globalAlpha = p.alpha;
        ctx.fillStyle = p.highlighted ? "#2563EB" : "#64748B";
        ctx.fillRect(p.x, p.y, 2, 4);

        if (mode === "stream") {
          p.y += p.vy;
          p.x += p.vx;
          if (p.y < -10) { p.y = H + 10; p.x = Math.random() * W; }
        } else {
          // settle: decay velocity
          p.vy *= 0.98;
          p.vx *= 0.98;
          p.y += p.vy;
          p.x += p.vx;
          // gentle oscillation
          p.x += Math.sin(Date.now() * 0.001 + p.x) * 0.05;
        }
      }
      ctx.globalAlpha = 1;
      rafId = requestAnimationFrame(draw);
    }

    draw();
    return () => cancelAnimationFrame(rafId);
  }, [mode, highlightRatio, reducedMotion]);

  if (reducedMotion) {
    return (
      <div
        className={cn("absolute inset-0", className)}
        style={{ background: "#0B1220" }}
        aria-hidden="true"
      />
    );
  }

  return (
    <canvas
      ref={canvasRef}
      className={cn("absolute inset-0 h-full w-full", className)}
      style={{ willChange: "transform" }}
      aria-hidden="true"
    />
  );
}
```

### 2.2 `SceneTitle` component

**File:** `UI/components/demo/scene-title.tsx`

```tsx
"use client";
import { cn } from "@/lib/utils";
import { useEffect, useState } from "react";

type SceneTitleProps = {
  title: string;
  subtitle?: string;
  stat?: string;
  className?: string;
};

export function SceneTitle({ title, subtitle, stat, className }: SceneTitleProps) {
  const [visible, setVisible] = useState(false);
  const [statVisible, setStatVisible] = useState(false);

  useEffect(() => {
    const t1 = setTimeout(() => setVisible(true), 200);
    const t2 = setTimeout(() => setStatVisible(true), 2000);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, []);

  return (
    <div className={cn("relative z-10 flex flex-col items-center justify-center h-full px-12 text-center", className)}>
      <h1
        className={cn(
          "text-4xl md:text-5xl font-bold tracking-tight text-white max-w-3xl transition-all duration-[1500ms]",
          visible ? "opacity-100 blur-0" : "opacity-0 blur-[8px]"
        )}
      >
        {title}
      </h1>
      {subtitle && (
        <p
          className={cn(
            "mt-4 text-lg text-white/60 max-w-xl transition-all duration-500 delay-500",
            visible ? "opacity-100" : "opacity-0"
          )}
        >
          {subtitle}
        </p>
      )}
      {stat && (
        <div
          className={cn(
            "absolute bottom-8 right-8 font-mono text-sm uppercase tracking-widest text-primary",
            "transition-opacity duration-500",
            statVisible ? "opacity-100" : "opacity-0"
          )}
        >
          {stat}
        </div>
      )}
    </div>
  );
}
```

### 2.3 Scene 01 assembly

**File:** `UI/features/demo/scene-01-cold-open.tsx`

```tsx
"use client";
import { ParticleField } from "@/components/demo/particle-field";
import { SceneTitle } from "@/components/demo/scene-title";
import type { SceneProps } from "./scene-registry";

export const scene01SpeakerNotes = `
0:00–0:40. Lights low. Let the particle field run 2 seconds before speaking.
"Last year, your business processed millions of transactions.
[beat] Your audit team looked at maybe five percent of them.
[long beat] This is the story of the other ninety-five."
(cue) Hard cut to Scene 04 (or Scene 02 in 10-min cut).
`;

export function Scene01ColdOpen({ isActive }: SceneProps) {
  if (!isActive) return null;
  return (
    <div className="relative h-screen w-screen overflow-hidden bg-[#0B1220]">
      <ParticleField mode="stream" highlightRatio={0.05} />
      <SceneTitle
        title="Every transaction is a question no one has time to ask."
        subtitle="Last year, your business processed millions of transactions."
        stat="~5% sampled"
      />
    </div>
  );
}
```

---

## Step 3 — Scene 04: Vision reveal (Day 3, morning)

### 3.1 `DayBreakWipe` CSS animation

Add to **`UI/app/globals.css`**:

```css
@keyframes day-break-wipe {
  from {
    background-color: #0B1220;
    clip-path: inset(0 100% 0 0);
  }
  to {
    background-color: #F5F7FB;
    clip-path: inset(0 0% 0 0);
  }
}

.animate-day-break {
  animation: day-break-wipe 800ms cubic-bezier(0.4, 0, 0.2, 1) forwards;
}
```

### 3.2 Scene 04 assembly

**File:** `UI/features/demo/scene-04-vision.tsx`

```tsx
"use client";
import { useEffect, useState } from "react";
import { ParticleField } from "@/components/demo/particle-field";
import { cn } from "@/lib/utils";
import type { SceneProps } from "./scene-registry";

export const scene04SpeakerNotes = `
2:00–2:40. Music lifts. Particles converge into the logo.
"So we asked a simple question: what if every flagged transaction got a fair trial?
[beat] Not one AI with one opinion — because opinions hallucinate.
A real argument. Evidence. A verdict. And a human with the final say.
[beat] This is GL Guardian."
(cue) Advance to Scene 05.
`;

export function Scene04Vision({ isActive }: SceneProps) {
  const [phase, setPhase] = useState<"dark" | "wipe" | "light">("dark");
  const [logoVisible, setLogoVisible] = useState(false);
  const [taglineVisible, setTaglineVisible] = useState(false);

  useEffect(() => {
    if (!isActive) return;
    const t1 = setTimeout(() => setPhase("wipe"), 500);
    const t2 = setTimeout(() => setPhase("light"), 1300);
    const t3 = setTimeout(() => setLogoVisible(true), 2000);
    const t4 = setTimeout(() => setTaglineVisible(true), 2400);
    return () => [t1, t2, t3, t4].forEach(clearTimeout);
  }, [isActive]);

  if (!isActive) return null;

  return (
    <div
      className={cn(
        "relative h-screen w-screen overflow-hidden transition-colors duration-700",
        phase === "dark" || phase === "wipe" ? "bg-[#0B1220]" : "bg-[#F5F7FB]",
        phase === "wipe" && "animate-day-break"
      )}
    >
      <ParticleField
        mode={phase === "light" ? "settle" : "stream"}
        highlightRatio={phase === "light" ? 0.8 : 0.05}
        className={cn("transition-opacity duration-700", phase === "light" ? "opacity-20" : "opacity-100")}
      />

      {/* Logo + tagline on light background */}
      {phase === "light" && (
        <div className="relative z-10 flex flex-col items-center justify-center h-full gap-6">
          <div
            className={cn(
              "transition-all duration-500",
              logoVisible ? "opacity-100 scale-100" : "opacity-0 scale-95"
            )}
          >
            {/* Replace with actual <Image> logo when available */}
            <span className="text-4xl font-bold tracking-tight text-[#0B1220]">
              GL Guardian
            </span>
          </div>
          <p
            className={cn(
              "text-lg text-[#151A2D]/70 transition-opacity duration-500",
              taglineVisible ? "opacity-100" : "opacity-0"
            )}
          >
            Every transaction gets a fair trial.
          </p>
        </div>
      )}
    </div>
  );
}
```


---

## Step 4 — Scene 06: The debate (Days 4–5)

This is the highest-priority scene. Spend two full days on it.

### 4.1 Demo debate fixture

**File:** `UI/data/demo/demo-debate.ts`

```ts
import type { DebateArgument } from "@/types/domain";

// Scripted confidence sequence: 0.5 → 0.42 → 0.61 → 0.55 → 0.78 → 0.83
// The Challenger suppresses confidence; the Defender recovers it; the Adjudicator settles.

export const DEMO_DEBATE: DebateArgument[] = [
  {
    id: "demo-arg-01",
    side: "challenger",
    title: "Large wire to unverified entity",
    timestamp: "2024-11-15T09:14:22Z",
    summary:
      "Payment of $285,000 exceeds the materiality threshold of $250,000. " +
      "Vendor 'Maelstrom Corp GmbH' was added to the approved-vendor registry only 87 days ago. " +
      "Single-approver authorization for an amount this size violates the dual-control policy " +
      "in Section 4.2 of the Procurement Controls Standard.",
    tags: ["materiality", "new-vendor", "single-approver"],
    footer: "Round 1 · Challenger",
    scoreLabel: "0.42",
    citations: ["Procurement Controls Standard §4.2", "Vendor Registry API"],
    confidence: 0.42,
    details:
      "Full rule reference: PCS §4.2 requires dual authorization for wires above $200,000. " +
      "Vendor registry timestamp: 2024-08-20. Payment date: 2024-11-15. Delta: 87 days. " +
      "Dual-control policy exception requires CFO pre-approval on file — none found.",
  },
  {
    id: "demo-arg-02",
    side: "defender",
    title: "Vendor verified; contract on file",
    timestamp: "2024-11-15T09:14:55Z",
    summary:
      "Maelstrom Corp GmbH is registered in the EU commercial registry (HRB 221847). " +
      "A signed software-licensing agreement (Contract #SLA-2024-0318) covers this payment " +
      "as Milestone 2 of 4. The payment amount matches the contract schedule exactly. " +
      "FX rate deviation is within the 3% tolerance band per Finance Policy §6.1.",
    tags: ["vendor-verified", "contract", "fx-tolerance"],
    footer: "Round 1 · Defender",
    scoreLabel: "0.61",
    citations: ["EU Commercial Registry HRB 221847", "Contract SLA-2024-0318", "Finance Policy §6.1"],
    confidence: 0.61,
    details:
      "Contract SLA-2024-0318, Exhibit B, Milestone Schedule: Milestone 2 = $285,000 USD " +
      "due within 30 days of alpha delivery. Alpha delivery confirmed 2024-10-22. " +
      "FX rate on payment date (EUR/USD 1.0842) vs. contract rate (EUR/USD 1.0610): 2.2% deviation.",
  },
  {
    id: "demo-arg-03",
    side: "challenger",
    title: "FX rate claim not grounded in a source",
    timestamp: "2024-11-15T09:15:31Z",
    summary:
      "The Verifier rejected the FX rate citation as ungrounded: the referenced Finance Policy §6.1 " +
      "tolerance band applies to spot-rate hedging, not to invoice settlement. " +
      "The correct policy for invoice FX variance is §6.3, which sets a 1.5% tolerance. " +
      "At 2.2%, this payment is out-of-band.",
    tags: ["fx-variance", "verifier-rejected", "policy-mismatch"],
    footer: "Round 2 · Challenger",
    scoreLabel: "0.55",
    citations: ["Finance Policy §6.3"],
    confidence: 0.55,
    details:
      "Verifier log: 'Citation Finance Policy §6.1 does not apply to invoice settlement FX. " +
      "Claim marked unsupported. Correct reference is §6.3 (1.5% tolerance for invoice FX).' " +
      "Challenger notes the 2.2% deviation exceeds the corrected threshold by 0.7 percentage points.",
  },
  {
    id: "demo-arg-04",
    side: "defender",
    title: "Contract terms justify payment; FX delta immaterial",
    timestamp: "2024-11-15T09:16:08Z",
    summary:
      "Accepted. The correct reference is §6.3. However, the absolute FX delta is $5,985 — " +
      "well below the $25,000 financial-impact floor for mandatory review under §6.3(b). " +
      "Per clause 7.3 of Contract SLA-2024-0318, the vendor may invoice in EUR; the company bears FX risk. " +
      "Dual-control exception: CFO email approval on 2024-10-30 pre-authorized this milestone payment.",
    tags: ["fx-immaterial", "contract-clause-7.3", "cfo-approval"],
    footer: "Round 2 · Defender",
    scoreLabel: "0.78",
    citations: ["Finance Policy §6.3(b)", "Contract SLA-2024-0318 §7.3", "CFO Approval Email 2024-10-30"],
    confidence: 0.78,
    details:
      "CFO approval email (ref: CFO-2024-1030-0042) explicitly names Maelstrom Corp milestone payment. " +
      "§6.3(b) states: 'FX variances below $25,000 absolute impact do not require escalation.' " +
      "Absolute FX delta: $285,000 × 0.7% excess = $1,995. Well within the floor.",
  },
  {
    id: "demo-arg-05",
    side: "adjudicator",
    title: "Cleared with conditions — vendor legitimate",
    timestamp: "2024-11-15T09:16:55Z",
    summary:
      "Verdict: CLEARED WITH CONDITIONS. The payment is legitimate under Contract SLA-2024-0318. " +
      "CFO approval satisfies the dual-control requirement. FX delta is below the §6.3(b) floor. " +
      "Conditions: (1) Append CFO approval email to the vendor file for future audits. " +
      "(2) Monitor Maelstrom Corp for 90 days — vendor is still within the new-vendor window.",
    tags: ["cleared", "conditions", "monitoring"],
    footer: "Adjudicator · Final verdict",
    scoreLabel: "0.83",
    citations: ["Contract SLA-2024-0318", "CFO Approval Email 2024-10-30", "Finance Policy §6.3(b)"],
    confidence: 0.83,
    details:
      "Risk adjudication rationale: two rounds of adversarial pressure surfaced the correct policy " +
      "reference (§6.3 vs §6.1) and the CFO approval. Both conditions above must be completed " +
      "by the assigned reviewer before the case is closed. Confidence 0.83 → routes to Human Review lane.",
  },
];
```

### 4.2 Extended `DebateView` props

Add `demoMode` and `streamMessages` props to the existing `DebateView` without breaking existing usage:

**File:** `UI/features/debate/debate-view.tsx` — add to the top of the component:

```tsx
// New props interface (add alongside existing):
type DebateViewerDemoProps = {
  demoMode?: boolean;
  streamMessages?: boolean;
};

// In the component body, before the data fetch:
const { demoDebate } = demoMode ? useDemoMode() : { demoDebate: [] };
const effectiveData = demoMode ? demoDebate : data;
```

> Keep the diff minimal. The existing `DebateView` API is unchanged when `demoMode` is not passed.

### 4.3 `VerdictCard` component

**File:** `UI/components/demo/verdict-card.tsx`

```tsx
"use client";
import { Gavel } from "lucide-react";
import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ConfidenceMeter } from "@/components/shared/confidence-meter";
import { cn } from "@/lib/utils";
import type { DebateArgument } from "@/types/domain";

type VerdictCardProps = {
  verdict: DebateArgument;
  visible?: boolean;
};

export function VerdictCard({ verdict, visible = false }: VerdictCardProps) {
  const [entered, setEntered] = useState(false);
  const [gavelDrop, setGavelDrop] = useState(false);

  useEffect(() => {
    if (!visible) return;
    const t1 = setTimeout(() => setEntered(true), 200);
    const t2 = setTimeout(() => setGavelDrop(true), 400);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [visible]);

  return (
    <Card
      className={cn(
        "border-l-4 border-l-primary shadow-panel transition-all duration-500",
        entered ? "opacity-100 scale-100" : "opacity-0 scale-95"
      )}
    >
      <CardContent className="p-4">
        <div className="flex items-center gap-2">
          <Gavel
            className={cn(
              "h-5 w-5 text-primary transition-transform duration-300",
              gavelDrop ? "rotate-0" : "-rotate-[15deg]"
            )}
            aria-hidden="true"
          />
          <h2 className="text-sm font-semibold text-foreground">
            Adjudicator verdict
          </h2>
          <Badge variant="primary">{verdict.title}</Badge>
        </div>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          {verdict.summary}
        </p>
        {typeof verdict.confidence === "number" && (
          <ConfidenceMeter
            value={verdict.confidence}
            label="Verdict confidence"
            className="mt-4 max-w-sm"
            aria-valuenow={verdict.confidence}
            aria-valuemin={0}
            aria-valuemax={1}
          />
        )}
      </CardContent>
    </Card>
  );
}
```

### 4.4 Word-by-word streaming hook

**File:** `UI/hooks/use-word-stream.ts`

```ts
import { useState, useEffect } from "react";

export function useWordStream(text: string, active: boolean, intervalMs = 60) {
  const words = text.split(" ");
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (!active) return;
    // Respect prefers-reduced-motion
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reducedMotion) { setCount(words.length); return; }

    const id = setInterval(() => {
      setCount(c => {
        if (c >= words.length) { clearInterval(id); return c; }
        return c + 1;
      });
    }, intervalMs);
    return () => clearInterval(id);
  }, [active, words.length, intervalMs]);

  return {
    displayText: words.slice(0, count).join(" "),
    isComplete: count >= words.length,
  };
}
```

### 4.5 Scene 06 assembly

**File:** `UI/features/demo/scene-06-debate.tsx`

```tsx
"use client";
import { useState, useEffect } from "react";
import { DebateMessage } from "@/components/debate/debate-message";
import { VerdictCard } from "@/components/demo/verdict-card";
import { ConfidenceMeter } from "@/components/shared/confidence-meter";
import { useDemoMode } from "@/hooks/use-demo-mode";
import type { SceneProps } from "./scene-registry";

// Scripted confidence values matched to argument index
const CONFIDENCE_SEQUENCE = [0.5, 0.42, 0.61, 0.55, 0.78, 0.83];

export const scene06SpeakerNotes = `
3:30–4:30. THE moment. SLOW DOWN. Let the arguments type in.
"Here's what makes it different. The Challenger builds the case that this is fraud.
The Defender builds the case that it's a legitimate business transaction.
They go up to two rounds — pressure-testing each other.
[beat] And neither one gets the last word. [long beat] The Adjudicator does."
(cue) Gavel drops; meter settles.
Audience: "Have you ever seen AI argue with itself before?" [beat] Dissolve to next scene.
`;

export function Scene06Debate({ isActive, demoMode }: SceneProps) {
  const { demoDebate } = useDemoMode();
  const [visibleCount, setVisibleCount] = useState(0);
  const [confidence, setConfidence] = useState(CONFIDENCE_SEQUENCE[0]);

  // Advance one argument every ~4 seconds in demo mode
  useEffect(() => {
    if (!isActive) return;
    setVisibleCount(0);
    setConfidence(CONFIDENCE_SEQUENCE[0]);
    const id = setInterval(() => {
      setVisibleCount(n => {
        const next = Math.min(n + 1, demoDebate.length);
        setConfidence(CONFIDENCE_SEQUENCE[next] ?? confidence);
        return next;
      });
    }, 4000);
    return () => clearInterval(id);
  }, [isActive]);

  const visible = demoDebate.slice(0, visibleCount);
  const challengers = visible.filter(a => a.side === "challenger");
  const defenders = visible.filter(a => a.side === "defender");
  const verdict = visible.find(a => a.side === "adjudicator");

  return (
    <div className="h-screen w-screen overflow-y-auto bg-background p-6 md:p-10">
      <h1 className="mb-6 text-2xl font-bold text-foreground">
        The debate: Challenger vs. Defender
      </h1>

      {/* Confidence meter — between the two columns */}
      <ConfidenceMeter
        value={confidence}
        label="Live confidence"
        className="mb-6 max-w-md mx-auto"
        aria-valuenow={confidence}
        aria-valuemin={0}
        aria-valuemax={1}
      />

      {/* Debate transcript — aria-live for screen reader announcements */}
      <div
        role="log"
        aria-live="polite"
        aria-label="Debate transcript"
        className="grid gap-6 md:grid-cols-2"
      >
        {/* Challenger column */}
        <div className="space-y-4">
          <h2 className="text-sm font-semibold text-danger-foreground">
            Challenger view
            <span className="ml-2 text-xs font-normal text-muted-foreground">
              worst-case risk
            </span>
          </h2>
          {challengers.map(arg => (
            <DebateMessage key={arg.id} argument={arg} />
          ))}
        </div>

        {/* Defender column */}
        <div className="space-y-4">
          <h2 className="text-sm font-semibold text-success-foreground">
            Defender view
            <span className="ml-2 text-xs font-normal text-muted-foreground">
              legitimate rationale
            </span>
          </h2>
          {defenders.map(arg => (
            <DebateMessage key={arg.id} argument={arg} />
          ))}
        </div>
      </div>

      {/* Verdict */}
      {verdict && (
        <div className="mt-8">
          <VerdictCard verdict={verdict} visible={true} />
        </div>
      )}
    </div>
  );
}
```


---

## Step 5 — Scene 10: Live product (Day 6)

Scene 10 is the "proof moment." It must show the real product UI, not a mockup.

### 5.1 Demo mode flag in existing hooks

Add a `demoMode` guard to `use-investigation-realtime.ts` so the WebSocket doesn't reconnect during the live demo:

```ts
// UI/hooks/use-investigation-realtime.ts — add near the top:
const { enabled: demoModeEnabled } = useDemoMode();

// In the useEffect that opens the WebSocket:
if (demoModeEnabled) return; // skip realtime subscription in demo mode
```

### 5.2 Seeded demo case in intake route

In `UI/app/(app)/intake/page.tsx` (or the intake feature component), check for `?demo=1` and pre-populate the case:

```tsx
// UI/features/intake/intake-view.tsx — add near data-fetch logic:
const searchParams = useSearchParams();
const isDemoMode = searchParams.get("demo") === "1";
const { demoCase } = useDemoMode();

// If demo mode, skip the CSV upload step and show the pre-populated case directly
if (isDemoMode) {
  // Render the flagged-rows preview with DEMO_CASE data instead of the CSV uploader
  return <IntakeDemoPreview demoCase={demoCase} />;
}
```

### 5.3 Scene 10 assembly

**File:** `UI/features/demo/scene-10-live-product.tsx`

```tsx
"use client";
import { useState } from "react";
import { cn } from "@/lib/utils";
import type { SceneProps } from "./scene-registry";

type Step = {
  id: number;
  label: string;
  path: string;
};

const DEMO_STEPS: Step[] = [
  { id: 1, label: "Intake", path: "/intake?demo=1" },
  { id: 2, label: "Dashboard", path: "/dashboard?demo=1" },
  { id: 3, label: "Workspace", path: "/investigations/demo-case-001?demo=1" },
  { id: 4, label: "Review", path: "/human-review?demo=1" },
  { id: 5, label: "Report", path: "/reports?demo=1" },
];

export const scene10SpeakerNotes = `
6:40–7:40. START THE RECORDING (or click through live).
"And this is the actual product.
Upload a ledger. [beat] Watch the cases populate.
Open one, and you get the whole story — pipeline status, evidence, the debate transcript,
the verification checklist, your review actions.
Approve — [beat] — and the report generates itself."
(cue) Pull back from the device.
FALLBACK: If network is shaky, switch to the recorded walkthrough — never debug on stage.
`;

export function Scene10LiveProduct({ isActive }: SceneProps) {
  const [activeStep, setActiveStep] = useState(0);

  if (!isActive) return null;

  const current = DEMO_STEPS[activeStep];

  return (
    <div className="relative h-screen w-screen overflow-hidden bg-[#F5F7FB] flex flex-col">
      {/* Route breadcrumb chips */}
      <div className="flex items-center gap-2 px-8 py-4 bg-white border-b border-border">
        {DEMO_STEPS.map((step, i) => (
          <button
            key={step.id}
            onClick={e => { e.stopPropagation(); setActiveStep(i); }}
            className={cn(
              "rounded-full px-3 py-1 text-xs font-medium transition-colors",
              i === activeStep
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            )}
          >
            {step.id}. {step.label}
          </button>
        ))}
      </div>

      {/* Device frame — embeds the real app in an iframe */}
      <div className="flex flex-1 items-center justify-center p-8">
        <div className="w-full max-w-5xl rounded-xl border border-border shadow-panel overflow-hidden bg-white"
          style={{ height: "calc(100vh - 160px)" }}>
          <iframe
            src={current.path}
            className="h-full w-full border-0"
            title={`Demo — ${current.label}`}
          />
        </div>
      </div>
    </div>
  );
}
```

> **Note on iframes:** If CSP headers block same-origin iframes, replace with a direct Next.js Link navigation and a back button. The scene structure stays the same.

---

## Step 6 — Scene 14: Close / CTA (Day 3, afternoon)

**File:** `UI/features/demo/scene-14-cta.tsx`

```tsx
"use client";
import { useEffect, useState } from "react";
import { ParticleField } from "@/components/demo/particle-field";
import { cn } from "@/lib/utils";
import type { SceneProps } from "./scene-registry";

export const scene14SpeakerNotes = `
9:35–10:00. Back to dark. Logo + CTA. Particles settle.
"GL Guardian.
Every transaction gets a fair trial — cited, argued, verified, and signed.
[beat] Let's run it on your data.
[beat] Where should we start?"
(cue) Hold on the logo. End.
`;

export function Scene14CTA({ isActive }: SceneProps) {
  const [phase, setPhase] = useState(0);
  // phase 0 = nothing, 1 = logo, 2 = tagline, 3 = CTA text, 4 = question, 5 = button pulse

  useEffect(() => {
    if (!isActive) return;
    const timings = [400, 800, 1400, 2200, 3000];
    const ids = timings.map((t, i) =>
      setTimeout(() => setPhase(i + 1), t)
    );
    return () => ids.forEach(clearTimeout);
  }, [isActive]);

  if (!isActive) return null;

  return (
    <div className="relative h-screen w-screen overflow-hidden bg-[#0B1220]">
      <ParticleField mode="settle" highlightRatio={0.15} />

      <div className="relative z-10 flex flex-col items-center justify-center h-full gap-6 px-8 text-center">
        {/* Logo */}
        <div className={cn(
          "transition-all duration-500",
          phase >= 1 ? "opacity-100 translate-y-0" : "opacity-0 translate-y-2"
        )}>
          <span className="text-3xl font-bold text-white tracking-tight">
            GL Guardian
          </span>
        </div>

        {/* Tagline */}
        <p className={cn(
          "max-w-lg text-base text-white/60 leading-7 transition-opacity duration-500",
          phase >= 2 ? "opacity-100" : "opacity-0"
        )}>
          Every transaction gets a fair trial — cited, argued, verified, and signed.
        </p>

        {/* CTA text */}
        <p className={cn(
          "text-3xl font-semibold text-white transition-all duration-500",
          phase >= 3 ? "opacity-100 translate-y-0" : "opacity-0 translate-y-2"
        )}>
          Let&apos;s run it on your data.
        </p>

        {/* Question */}
        <p className={cn(
          "text-xl text-white/70 transition-opacity duration-500",
          phase >= 4 ? "opacity-100" : "opacity-0"
        )}>
          Where should we start?
        </p>

        {/* CTA button — pulses once */}
        <button
          type="button"
          className={cn(
            "mt-2 rounded-md bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground",
            "transition-all duration-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            phase === 5
              ? "scale-104"  // pulse peak
              : phase >= 4
                ? "scale-100"
                : "opacity-0 scale-95"
          )}
          onClick={e => e.stopPropagation()}
        >
          Book a live investigation
        </button>
      </div>
    </div>
  );
}
```

---

## Step 7 — Wiring everything together (Day 7)

### 7.1 Scene registry

**File:** `UI/features/demo/scene-registry.ts`

```ts
import type { ComponentType } from "react";

export type SceneProps = {
  isActive: boolean;
  demoMode?: boolean;
};

export type DemoScene = {
  id: string;
  name: string;
  duration: number; // seconds
  inCut: "10min" | "5min" | "both";
  component: ComponentType<SceneProps>;
  speakerNotes: string;
};

// Import lazily to keep the initial bundle small
import dynamic from "next/dynamic";
import { scene01SpeakerNotes } from "./scene-01-cold-open";
import { scene04SpeakerNotes } from "./scene-04-vision";
import { scene06SpeakerNotes } from "./scene-06-debate";
import { scene10SpeakerNotes } from "./scene-10-live-product";
import { scene14SpeakerNotes } from "./scene-14-cta";

const Scene01 = dynamic(() => import("./scene-01-cold-open").then(m => ({ default: m.Scene01ColdOpen })));
const Scene04 = dynamic(() => import("./scene-04-vision").then(m => ({ default: m.Scene04Vision })));
const Scene06 = dynamic(() => import("./scene-06-debate").then(m => ({ default: m.Scene06Debate })));
const Scene10 = dynamic(() => import("./scene-10-live-product").then(m => ({ default: m.Scene10LiveProduct })));
const Scene14 = dynamic(() => import("./scene-14-cta").then(m => ({ default: m.Scene14CTA })));

export const ALL_SCENES: DemoScene[] = [
  { id: "01", name: "Cold open", duration: 40, inCut: "both", component: Scene01, speakerNotes: scene01SpeakerNotes },
  { id: "04", name: "Vision", duration: 40, inCut: "both", component: Scene04, speakerNotes: scene04SpeakerNotes },
  { id: "06", name: "The debate", duration: 60, inCut: "both", component: Scene06, speakerNotes: scene06SpeakerNotes },
  { id: "10", name: "Live product", duration: 60, inCut: "both", component: Scene10, speakerNotes: scene10SpeakerNotes },
  { id: "14", name: "CTA", duration: 25, inCut: "both", component: Scene14, speakerNotes: scene14SpeakerNotes },
];

export const FIVE_MIN_SCENES = ALL_SCENES.filter(s => s.inCut === "both" || s.inCut === "5min");
```

### 7.2 Demo page entry point

**File:** `UI/app/(demo)/demo/page.tsx`

```tsx
import { Suspense } from "react";
import { DemoShell } from "@/features/demo/demo-shell";
import { DemoModeProvider } from "@/hooks/use-demo-mode";
import { ALL_SCENES, FIVE_MIN_SCENES } from "@/features/demo/scene-registry";

type Props = {
  searchParams: { scene?: string; cut?: string; notes?: string };
};

export default function DemoPage({ searchParams }: Props) {
  const scenes = searchParams.cut === "5min" ? FIVE_MIN_SCENES : ALL_SCENES;
  const initialSceneId = searchParams.scene;
  const notesMode = searchParams.notes === "1";

  return (
    <DemoModeProvider initialEnabled={true}>
      <Suspense>
        <DemoShell
          scenes={scenes}
          initialSceneId={initialSceneId}
          notesMode={notesMode}
        />
      </Suspense>
    </DemoModeProvider>
  );
}
```

---

## Pre-Demo Rehearsal Checklist

Run this before any live demo:

### Technical checks (5 minutes before showtime)
- [ ] Open `/demo?demo=1&cut=5min` — all 5 scenes load without errors
- [ ] Press right arrow 5 times — all scenes transition cleanly
- [ ] Scene 06: debate streams all 5 arguments; gavel drops; meter settles at 0.83
- [ ] Scene 10: `?demo=1` seeds Maelstrom Corp case; workspace shows debate viewer
- [ ] Scene 14: CTA button pulses once; "Where should we start?" is visible last
- [ ] Browser console: zero errors
- [ ] Network: test on the venue wifi; if latency >200ms, switch Scene 10 to `mode="recording"`

### Fallback plan
- Recording fallback: `/demo?demo=1&scene=10` → set `mode="recording"` via a URL param or config
- If the whole app is down: present `GL_Guardian_Presentation.pptx` with recorded Scene 10 embedded
- Backup URL on mobile hotspot: keep a hotspot ready

### Presenter notes
- [ ] `?notes=1` mode tested — speaker notes visible at correct opacity
- [ ] `?` key toggles notes overlay
- [ ] `Escape` exits to dashboard (not the browser tab)
- [ ] 5-minute cut timing: rehearsed within ±20s of 5:00

### Story checks
- [ ] Scene 01 creates genuine unease ("there is a huge blind spot")
- [ ] Scene 06 lands the "Have you ever seen AI argue with itself?" reaction
- [ ] Scene 14 ends on a question, not a statement and not "thank you"
- [ ] Every red element = Challenger/risk; every green = Defender/verified (no decorative color)
