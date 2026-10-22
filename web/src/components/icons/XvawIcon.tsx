import { forwardRef, type SVGProps } from "react";

/** Xvaw's flowing signal ribbons, legible at launcher and inline sizes. */
export const XvawIcon = forwardRef<SVGSVGElement, SVGProps<SVGSVGElement>>(
  function XvawIcon(props, ref) {
    return (
      <svg ref={ref} viewBox="0 0 128 128" fill="none" aria-hidden="true" {...props}>
        <rect width="128" height="128" rx="32" fill="#101923" />
        <path
          d="M32 39C44 29 55 29 68 36C81 43 92 43 104 33V47C92 57 81 57 68 50C55 43 44 43 32 53Z"
          fill="#6EE7D2"
        />
        <path
          d="M24 61C36 51 47 51 60 58C73 65 84 65 96 55V69C84 79 73 79 60 72C47 65 36 65 24 75Z"
          fill="#E8FFF9"
        />
        <path
          d="M32 83C44 73 55 73 68 80C81 87 92 87 104 77V91C92 101 81 101 68 94C55 87 44 87 32 97Z"
          fill="#89A9FF"
        />
      </svg>
    );
  },
);
