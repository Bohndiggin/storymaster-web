import { forwardRef, type TextareaHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, rows = 3, ...rest }, ref) => (
    <textarea
      ref={ref}
      rows={rows}
      className={cn(
        "w-full rounded-md border border-slate-700 bg-canvas-panel p-3 text-sm text-slate-100 placeholder:text-slate-500",
        "focus:outline-none focus:ring-2 focus:ring-accent",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...rest}
    />
  ),
);
Textarea.displayName = "Textarea";
