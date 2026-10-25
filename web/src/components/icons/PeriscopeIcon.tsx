import type { SVGProps } from "react";

export function PeriscopeIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      <path d="M7 21V11a6 6 0 0 1 6-6h3M12 21V12a2 2 0 0 1 2-2h2M5 21h9" />
      <rect x="16" y="3" width="4" height="9" rx="1" />
      <path d="M4 5h3M5.5 3.5v3" />
    </svg>
  );
}
