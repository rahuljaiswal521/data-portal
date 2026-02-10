"use client";

import { cn } from "@/lib/utils";
import { forwardRef, type InputHTMLAttributes } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, hint, id, ...props }, ref) => {
    const inputId = id || label?.toLowerCase().replace(/\s+/g, "-");
    return (
      <div className="space-y-1.5">
        {label && (
          <label
            htmlFor={inputId}
            className="block text-sm font-medium text-text-primary"
          >
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          className={cn(
            "w-full rounded-[var(--radius-md)] border bg-bg-card px-3 py-2 text-sm",
            "text-text-primary placeholder:text-text-tertiary",
            "transition-colors duration-150",
            "focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent",
            error
              ? "border-error"
              : "border-border hover:border-border-hover",
            className
          )}
          {...props}
        />
        {hint && !error && (
          <p className="text-xs text-text-tertiary">{hint}</p>
        )}
        {error && <p className="text-xs text-error">{error}</p>}
      </div>
    );
  }
);

Input.displayName = "Input";
