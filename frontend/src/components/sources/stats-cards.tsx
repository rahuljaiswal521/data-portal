"use client";

import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { DashboardStats } from "@/types";
import { Database, Power, PowerOff, AlertTriangle } from "lucide-react";

interface StatsCardsProps {
  stats?: DashboardStats;
  loading: boolean;
}

const cards = [
  {
    key: "total",
    label: "Total Sources",
    icon: Database,
    getValue: (s: DashboardStats) => s.total_sources,
    color: "text-text-primary",
  },
  {
    key: "enabled",
    label: "Enabled",
    icon: Power,
    getValue: (s: DashboardStats) => s.enabled_sources,
    color: "text-success",
  },
  {
    key: "disabled",
    label: "Disabled",
    icon: PowerOff,
    getValue: (s: DashboardStats) => s.disabled_sources,
    color: "text-text-tertiary",
  },
  {
    key: "failures",
    label: "Failures (24h)",
    icon: AlertTriangle,
    getValue: (s: DashboardStats) => s.recent_failures,
    color: "text-error",
  },
] as const;

export function StatsCards({ stats, loading }: StatsCardsProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((card) => (
        <Card key={card.key} className="flex items-center gap-4">
          <div className="flex items-center justify-center w-10 h-10 rounded-[var(--radius-md)] bg-bg-secondary">
            <card.icon size={18} className="text-text-secondary" />
          </div>
          <div>
            <p className="text-xs text-text-tertiary font-medium uppercase tracking-wide">
              {card.label}
            </p>
            {loading ? (
              <Skeleton className="h-7 w-12 mt-0.5" />
            ) : (
              <p className={`text-2xl font-semibold ${card.color}`}>
                {stats ? card.getValue(stats) : 0}
              </p>
            )}
          </div>
        </Card>
      ))}
    </div>
  );
}
