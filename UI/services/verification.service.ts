import { mockVerificationClaims } from "@/data/mock-verification";
import type { VerificationClaim } from "@/types/domain";

export async function getVerificationClaims(): Promise<VerificationClaim[]> {
  return mockVerificationClaims;
}
