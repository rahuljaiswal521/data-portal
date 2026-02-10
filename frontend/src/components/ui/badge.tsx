import { cn } from "@/lib/utils";

type Variant = "default" | "accent" | "success" | "warning" | "error" | "info";

const variantStyles: Record<Variant, string> = {
  default: "bg-bg-secondary text-text-secondary",
  accent: "bg-accent-light text-accent",
  success: "bg-[rgba(58,125,68,0.1)] text-success",
  warning: "bg-[rgba(196,135,59,0.1)] text-warning",
  error: "bg-[rgba(196,75,59,0.1)] text-error",
  info: "bg-[rgba(59,123,196,0.1)] text-info",
};

interface BadgeProps {
  children: React.ReactNode;
  variant?: Variant;
  className?: string;
}

export function Badge({ children, variant = "default", className }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-[var(--radius-full)] px-2.5 py-0.5 text-xs font-medium",
        variantStyles[variant],
        className
      )}
    >
      {children}
    </span>
  );
}
