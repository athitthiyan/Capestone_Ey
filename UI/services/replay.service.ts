import { mockReplayFrames } from "@/data/mock-replay";
import type { ReplayFrame } from "@/types/domain";

export async function getReplayFrames(): Promise<ReplayFrame[]> {
  return mockReplayFrames;
}
