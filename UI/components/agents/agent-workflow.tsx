"use client";

import "reactflow/dist/style.css";

import ReactFlow, {
  Background,
  ControlButton,
  Controls,
  Handle,
  MiniMap,
  Position,
  ReactFlowProvider,
  useNodesInitialized,
  useReactFlow,
  type Edge,
  type FitViewOptions,
  type Node,
  type NodeProps,
} from "reactflow";
import { Maximize2, Minimize2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ConfidenceMeter } from "@/components/shared/confidence-meter";
import { StatusBadge } from "@/components/shared/status-badge";
import { cn } from "@/lib/utils";
import type { PipelineStep } from "@/types/domain";

type WorkflowNodeData = {
  step: PipelineStep;
};

function WorkflowNode({ data }: NodeProps<WorkflowNodeData>) {
  return (
    <div className="flex h-[285px] w-64 flex-col overflow-hidden rounded-lg border border-border bg-card p-3 shadow-card">
      <Handle type="target" position={Position.Left} className="!bg-primary" />
      <div className="flex shrink-0 items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-foreground">{data.step.role}</p>
          <p className="mt-1 line-clamp-2 text-xs leading-5 text-muted-foreground">{data.step.detail}</p>
        </div>
        <StatusBadge state={data.step.state} />
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 rounded-md border border-border bg-muted/40 p-2 text-[11px] text-muted-foreground">
        <span>
          Latency <span className="font-mono text-foreground">{data.step.latency ?? "n/a"}</span>
        </span>
        <span>
          Attempt <span className="font-mono text-foreground">{data.step.attempt}</span>
        </span>
        <span>
          Tokens <span className="font-mono text-foreground">{data.step.tokenUsage}</span>
        </span>
        <span>
          Cost <span className="font-mono text-foreground">${data.step.cost.toFixed(2)}</span>
        </span>
      </div>
      {typeof data.step.confidence === "number" ? (
        <ConfidenceMeter value={data.step.confidence} className="mt-3" />
      ) : null}
      <details className="mt-3 min-h-0 text-xs text-muted-foreground">
        <summary className="cursor-pointer text-primary">Expand details</summary>
        <p className="mt-2 max-h-24 overflow-y-auto pr-1 leading-5">{data.step.expandedDetail}</p>
      </details>
      <Handle type="source" position={Position.Right} className="!bg-primary" />
    </div>
  );
}

const nodeTypes = {
  workflow: WorkflowNode,
};

const fitViewOptions = {
  padding: 0.18,
  minZoom: 0.25,
  maxZoom: 1,
} satisfies FitViewOptions;
const nodeColumnSpacing = 310;
const nodeRowSpacing = 315;

function AgentWorkflowCanvas({ steps, className }: { steps: PipelineStep[]; className?: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const { fitView } = useReactFlow();
  const nodesInitialized = useNodesInitialized();

  const nodes = useMemo<Node<WorkflowNodeData>[]>(
    () =>
      steps.map((step, index) => ({
        id: step.id,
        type: "workflow",
        position: {
          x: (index % 4) * nodeColumnSpacing,
          y: Math.floor(index / 4) * nodeRowSpacing,
        },
        data: { step },
      })),
    [steps],
  );

  const fitSignature = useMemo(
    () => steps.map((step) => `${step.id}:${step.state}`).join("|"),
    [steps],
  );

  const edges = useMemo<Edge[]>(
    () =>
      // Pair each step with its immediate predecessor by zipping the array
      // against itself offset by one, rather than cross-referencing through
      // a separately-sliced array's index - keeps the predecessor lookup
      // correct even if `steps` is ever filtered/reordered upstream.
      steps.slice(1).map((step, index) => {
        const previous = steps[index];
        return {
          id: `${previous.id}-${step.id}`,
          source: previous.id,
          target: step.id,
          animated: step.state === "running" || step.state === "queued",
          style: { stroke: "hsl(var(--primary))" },
        };
      }),
    [steps],
  );

  // Keep local state in sync with the browser's fullscreen status (covers Esc).
  useEffect(() => {
    const handler = () => setIsFullscreen(document.fullscreenElement === containerRef.current);
    document.addEventListener("fullscreenchange", handler);
    return () => document.removeEventListener("fullscreenchange", handler);
  }, []);

  const toggleFullscreen = useCallback(() => {
    const el = containerRef.current;
    if (!el) {
      return;
    }
    if (document.fullscreenElement) {
      void document.exitFullscreen();
    } else {
      void el.requestFullscreen?.();
    }
  }, []);

  useEffect(() => {
    if (!nodesInitialized || nodes.length === 0) {
      return undefined;
    }

    const timeoutId = window.setTimeout(() => {
      void fitView({ ...fitViewOptions, duration: 250 });
    }, 0);

    return () => window.clearTimeout(timeoutId);
  }, [fitSignature, fitView, isFullscreen, nodes.length, nodesInitialized]);

  return (
    <div
      ref={containerRef}
      className={cn(
        "overflow-hidden rounded-lg border border-border bg-card",
        isFullscreen ? "h-screen w-screen rounded-none" : "h-[520px]",
        className,
      )}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={fitViewOptions}
        minZoom={0.25}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        onlyRenderVisibleElements
      >
        <Background color="hsl(var(--border))" gap={20} />
        <MiniMap pannable zoomable className="!bg-muted" />
        <Controls className="!border-border !bg-card !text-foreground">
          <ControlButton
            onClick={toggleFullscreen}
            title={isFullscreen ? "Exit full screen" : "View full screen"}
            aria-label={isFullscreen ? "Exit full screen" : "View full screen"}
          >
            {isFullscreen ? <Minimize2 /> : <Maximize2 />}
          </ControlButton>
        </Controls>
      </ReactFlow>
    </div>
  );
}

export function AgentWorkflow({ steps, className }: { steps: PipelineStep[]; className?: string }) {
  return (
    <ReactFlowProvider>
      <AgentWorkflowCanvas steps={steps} className={className} />
    </ReactFlowProvider>
  );
}
