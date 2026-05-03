"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useSilverEntities, useSilverStats } from "@/hooks/use-silver";
import type { SilverEntitySummary } from "@/types/silver";
import {
  Database,
  Layers,
  CheckCircle2,
  FolderOpen,
  Plus,
} from "lucide-react";
import Link from "next/link";

function SilverStatsCards({
  stats,
  loading,
}: {
  stats: any;
  loading: boolean;
}) {
  if (loading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
    );
  }

  const cards = [
    {
      label: "Total Entities",
      value: stats?.total_entities ?? 0,
      icon: Database,
    },
    {
      label: "Enabled",
      value: stats?.enabled_entities ?? 0,
      icon: CheckCircle2,
    },
    {
      label: "Domains",
      value: stats?.domains?.length ?? 0,
      icon: FolderOpen,
    },
    {
      label: "SCD2 Entities",
      value: stats?.entities_by_scd_type?.scd2 ?? 0,
      icon: Layers,
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((card) => (
        <Card key={card.label}>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-text-secondary">{card.label}</p>
              <p className="text-2xl font-semibold text-text-primary mt-1">
                {card.value}
              </p>
            </div>
            <div className="flex items-center justify-center w-10 h-10 rounded-[var(--radius-md)] bg-accent-light">
              <card.icon size={20} className="text-accent" />
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}

function ScdBadge({ type }: { type: string }) {
  return (
    <Badge variant={type === "scd2" ? "accent" : "default"}>
      {type.toUpperCase()}
    </Badge>
  );
}

function DomainSection({
  domain,
  entities,
}: {
  domain: string;
  entities: SilverEntitySummary[];
}) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <FolderOpen size={16} className="text-accent" />
        <h3 className="text-sm font-semibold text-text-primary uppercase tracking-wider">
          slv_{domain}
        </h3>
        <Badge variant="default">{entities.length}</Badge>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {entities.map((entity) => (
          <Link key={entity.name} href={`/silver/${entity.name}`}>
            <Card className="hover:border-border-hover hover:bg-bg-card-hover transition-colors cursor-pointer">
              <div className="flex items-start justify-between">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <h4 className="text-sm font-medium text-text-primary truncate">
                      {entity.name}
                    </h4>
                    <ScdBadge type={entity.scd_type} />
                  </div>
                  <p className="text-xs text-text-secondary mt-1 truncate">
                    {entity.description || "No description"}
                  </p>
                  <div className="flex items-center gap-3 mt-2">
                    <span className="text-xs text-text-tertiary">
                      {entity.source_count} source{entity.source_count !== 1 ? "s" : ""}
                    </span>
                    <span className="text-xs text-text-tertiary">
                      Keys: {entity.business_keys.join(", ")}
                    </span>
                  </div>
                </div>
                <Badge variant={entity.enabled ? "success" : "default"} className="ml-2 shrink-0">
                  {entity.enabled ? "On" : "Off"}
                </Badge>
              </div>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}

export default function SilverDashboard() {
  const { data: entityData, isLoading: entitiesLoading } = useSilverEntities();
  const { data: stats, isLoading: statsLoading } = useSilverStats();

  // Group entities by domain
  const entityByDomain: Record<string, SilverEntitySummary[]> = {};
  if (entityData?.entities) {
    for (const entity of entityData.entities) {
      if (!entityByDomain[entity.domain]) {
        entityByDomain[entity.domain] = [];
      }
      entityByDomain[entity.domain].push(entity);
    }
  }

  const sortedDomains = Object.keys(entityByDomain).sort();

  return (
    <div className="space-y-8">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-text-primary">
            Silver Entities
          </h1>
          <p className="text-sm text-text-secondary mt-1">
            Canonical business entities — cleaned, conformed, and domain-organized
          </p>
        </div>
        <Link href="/silver/new">
          <Button>
            <Plus size={16} />
            New Entity
          </Button>
        </Link>
      </div>

      {/* Stats */}
      <SilverStatsCards stats={stats} loading={statsLoading} />

      {/* Entity list grouped by domain */}
      {entitiesLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      ) : sortedDomains.length > 0 ? (
        <div className="space-y-8">
          {sortedDomains.map((domain) => (
            <DomainSection
              key={domain}
              domain={domain}
              entities={entityByDomain[domain]}
            />
          ))}
        </div>
      ) : (
        <Card>
          <div className="text-center py-12">
            <Database size={32} className="mx-auto text-text-tertiary mb-3" />
            <p className="text-text-secondary font-medium">
              No Silver entities configured yet
            </p>
            <p className="text-xs text-text-tertiary mt-1 max-w-md mx-auto">
              Use the AI Assistant to model Bronze tables into Silver entities,
              or create entity YAML configs manually in the silver_framework/conf/entities/ directory.
            </p>
          </div>
        </Card>
      )}
    </div>
  );
}
