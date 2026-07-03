"use client";

import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { apiWebSocketUrl } from "@/services/api";
import type { PipelineStep, WorkState } from "@/types/domain";

type UseInvestigationRealtimeOptions = {
  enabled?: boolean;
  onMessage?: (message: string) => void;
};

const AGENT_TO_STEP: Record<string, string> = {
  adjudicator: "adjudicator",
  challenger: "challenger",
  confidence_gate: "review",
  defender: "defender",
  evidence: "evidence",
  evidence_agent: "evidence",
  supervisor: "intake",
  verifier: "verifier",
};

const STAGE_TO_STEPS: Record<string, string[]> = {
  agent_debate: ["challenger", "defender", "adjudicator"],
  closed: ["report", "audit"],
  collecting_evidence: ["evidence"],
  confidence_gate: ["review"],
  human_review: ["review"],
  intake: ["intake"],
  report_ready: ["report", "audit"],
  verification: ["verifier"],
};

function realtimeState(value: unknown): WorkState {
  const state = String(value ?? "running");
  if (
    state === "done" ||
    state === "running" ||
    state === "queued" ||
    state === "review" ||
    state === "failed" ||
    state === "retry" ||
    state === "escalated"
  ) {
    return state;
  }
  return "running";
}

function stageStepIds(value: unknown) {
  return STAGE_TO_STEPS[String(value ?? "")] ?? [];
}

function patchWorkflowSteps(
  current: PipelineStep[] | undefined,
  event: Record<string, unknown>,
): PipelineStep[] | undefined {
  if (!current?.length) {
    return current;
  }

  if (event.type === "pipeline_stage") {
    const fromSteps = new Set(stageStepIds(event.from_stage));
    const toSteps = new Set(stageStepIds(event.to_stage));
    const toStage = String(event.to_stage ?? "");

    return current.map((step) => {
      if (toSteps.has(step.id)) {
        const state: WorkState = toStage === "human_review" ? "review" : "running";
        return {
          ...step,
          state,
        };
      }
      if (fromSteps.has(step.id) && (step.state === "running" || step.state === "queued")) {
        return { ...step, state: "done" };
      }
      return step;
    });
  }

  if (event.type === "agent_status") {
    const stepId = AGENT_TO_STEP[String(event.agent ?? "").toLowerCase()];
    if (!stepId) {
      return current;
    }
    const message = typeof event.message === "string" ? event.message : undefined;
    return current.map((step) =>
      step.id === stepId
        ? {
            ...step,
            state: realtimeState(event.state),
            detail: message || step.detail,
          }
        : step,
    );
  }

  if (event.type === "debate_message") {
    const stepId = AGENT_TO_STEP[String(event.speaker ?? "").toLowerCase()];
    if (!stepId) {
      return current;
    }
    return current.map((step) =>
      step.id === stepId
        ? {
            ...step,
            state: "done",
            detail: `Round ${String(event.round ?? "")}: message recorded.`,
          }
        : step,
    );
  }

  if (event.type === "verification") {
    return current.map((step) =>
      step.id === "verifier"
        ? {
            ...step,
            state: String(event.status ?? "").toLowerCase() === "failed" ? "failed" : "done",
          }
        : step,
    );
  }

  return current;
}

export function messageFromRealtimeEvent(value: unknown) {
  if (!value || typeof value !== "object") {
    return null;
  }

  const event = value as Record<string, unknown>;

  if (event.type === "ack") {
    return null;
  }
  if (event.type === "agent_status") {
    return [event.agent, event.state, event.message].filter(Boolean).join(" - ");
  }
  if (event.type === "pipeline_stage") {
    return `Pipeline moved from ${String(event.from_stage)} to ${String(event.to_stage)}.`;
  }
  if (event.type === "debate_message") {
    return `${String(event.speaker)} posted debate round ${String(event.round)}.`;
  }
  if (event.type === "verification") {
    return `Evidence verification completed: ${String(event.status)}.`;
  }

  return typeof event.type === "string" ? `Realtime event: ${event.type}` : null;
}

export function useInvestigationRealtime(
  caseId?: string,
  { enabled = true, onMessage }: UseInvestigationRealtimeOptions = {},
) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!enabled || !caseId || typeof WebSocket === "undefined") {
      return undefined;
    }

    let socket: WebSocket | null = null;
    let closedByEffect = false;
    let reconnectAttempt = 0;
    let reconnectTimer: number | undefined;
    const MAX_RECONNECT_ATTEMPTS = 8;
    // 1000 = normal closure (server intentionally ended the stream, e.g. case
    // complete) and 1008 = policy violation (unauthorized) - neither should
    // trigger an infinite reconnect loop.
    const NO_RETRY_CLOSE_CODES = new Set([1000, 1008]);

    const refreshCaseQueries = (payload?: Record<string, unknown>) => {
      if (payload) {
        queryClient.setQueryData<PipelineStep[]>(
          ["agent-workflow", caseId],
          (current) => patchWorkflowSteps(current, payload),
        );
      }

      const type = String(payload?.type ?? "");
      const shouldRefreshWorkspace =
        !payload ||
        type === "pipeline_stage" ||
        type === "debate_message" ||
        type === "verification" ||
        type === "review_queue";
      const shouldRefreshLists =
        !payload ||
        type === "pipeline_stage" ||
        type === "verification" ||
        type === "review_queue";

      void Promise.all([
        queryClient.invalidateQueries({ queryKey: ["agent-workflow", caseId] }),
        ...(shouldRefreshWorkspace
          ? [
              queryClient.invalidateQueries({ queryKey: ["case-workspace", caseId] }),
              queryClient.invalidateQueries({ queryKey: ["investigation", caseId] }),
            ]
          : []),
        ...(shouldRefreshLists
          ? [
              queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] }),
              queryClient.invalidateQueries({ queryKey: ["investigations"] }),
              queryClient.invalidateQueries({ queryKey: ["review-queue"] }),
              queryClient.invalidateQueries({ queryKey: ["reports"] }),
            ]
          : []),
      ]);
    };

    const connect = async () => {
      const url = await apiWebSocketUrl(`/ws/investigations/${caseId}`);
      if (!url || closedByEffect) {
        return;
      }

      socket = new WebSocket(url);

      socket.onopen = () => {
        reconnectAttempt = 0;
        socket?.send("subscribe");
      };
      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(String(event.data)) as unknown;
          const message = messageFromRealtimeEvent(payload);

          if (message) {
            onMessage?.(message);
            refreshCaseQueries(payload as Record<string, unknown>);
          }
        } catch {
          onMessage?.(String(event.data));
          refreshCaseQueries();
        }
      };
      socket.onerror = () => {
        onMessage?.("Realtime connection interrupted; reconnecting.");
      };
      socket.onclose = (event) => {
        if (closedByEffect || NO_RETRY_CLOSE_CODES.has(event.code)) {
          return;
        }
        if (reconnectAttempt >= MAX_RECONNECT_ATTEMPTS) {
          onMessage?.("Realtime connection lost; giving up after repeated retries.");
          return;
        }

        const delayMs = Math.min(1000 * 2 ** reconnectAttempt, 10_000);
        reconnectAttempt += 1;
        reconnectTimer = window.setTimeout(() => void connect(), delayMs);
      };
    };

    void connect();

    return () => {
      closedByEffect = true;
      if (reconnectTimer) {
        window.clearTimeout(reconnectTimer);
      }
      socket?.close();
    };
  }, [caseId, enabled, onMessage, queryClient]);
}
