"use client";

import { useQuery } from "@tanstack/react-query";
import { getReplayFrames } from "@/services/replay.service";

export function useReplayFrames(caseId: string) {
  return useQuery({
    queryKey: ["replay-frames", caseId],
    queryFn: getReplayFrames,
  });
}
