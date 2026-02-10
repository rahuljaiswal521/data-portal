import { Badge } from "@/components/ui/badge";

const typeColors: Record<string, "default" | "accent" | "info" | "warning"> = {
  jdbc: "info",
  file: "default",
  api: "accent",
  stream: "warning",
};

export function TypeBadge({ type }: { type: string }) {
  return (
    <Badge variant={typeColors[type] || "default"}>
      {type.toUpperCase()}
    </Badge>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const variant =
    status === "SUCCESS"
      ? "success"
      : status === "FAILURE"
      ? "error"
      : status === "RUNNING"
      ? "info"
      : "default";

  return <Badge variant={variant}>{status}</Badge>;
}

export function CdcBadge({ mode }: { mode: string }) {
  const variant =
    mode === "scd2" ? "accent" : mode === "upsert" ? "info" : "default";

  return (
    <Badge variant={variant}>
      {mode === "scd2" ? "SCD2" : mode.charAt(0).toUpperCase() + mode.slice(1)}
    </Badge>
  );
}

export function EnabledDot({ enabled }: { enabled: boolean }) {
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full ${
        enabled ? "bg-success" : "bg-text-tertiary"
      }`}
      title={enabled ? "Enabled" : "Disabled"}
    />
  );
}
