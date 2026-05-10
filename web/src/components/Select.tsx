import { forwardRef, type SelectHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, children, ...rest }, ref) => (
    <select
      ref={ref}
      className={cn(
        "h-10 w-full rounded-md border border-slate-700 bg-canvas-panel px-3 text-sm text-slate-100",
        "focus:outline-none focus:ring-2 focus:ring-accent",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...rest}
    >
      {children}
    </select>
  ),
);
Select.displayName = "Select";
