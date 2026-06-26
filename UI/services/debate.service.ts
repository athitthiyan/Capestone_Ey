import { mockDebateArguments } from "@/data/mock-debate";
import type { DebateArgument } from "@/types/domain";

export async function getDebateArguments(): Promise<DebateArgument[]> {
  return mockDebateArguments;
}
