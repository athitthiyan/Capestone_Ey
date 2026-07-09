import { cn } from "@/lib/utils";

/**
 * GL Guardian brand mark: shield (guardian) with ledger lines
 * resolving into a verified check (automated audit).
 * Inherits text color via `currentColor`; the check uses the brand teal.
 */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={cn("h-5 w-5", className)}
      aria-hidden="true"
    >
      <path
        d="M24 3 L42 9.8 V23 C42 34.6 34.4 42.4 24 45.5 C13.6 42.4 6 34.6 6 23 V9.8 Z"
        stroke="currentColor"
        strokeWidth="2.6"
        strokeLinejoin="round"
      />
      <path d="M15 16.5 H33" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" opacity="0.55" />
      <path d="M15 22.5 H27" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" opacity="0.55" />
      <path
        d="M15.5 28.5 L21.5 34.5 L33.5 21"
        stroke="#3EC6A0"
        strokeWidth="3.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
