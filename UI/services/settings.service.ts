import { mockSettings } from "@/data/mock-settings";
import type { AppSettings } from "@/types/domain";

export async function getSettings(): Promise<AppSettings> {
  return mockSettings;
}
