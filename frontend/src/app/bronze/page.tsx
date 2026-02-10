"use client";

import { Button } from "@/components/ui/button";
import { SourceTable } from "@/components/sources/source-table";
import { StatsCards } from "@/components/sources/stats-cards";
import { useDashboardStats, useSources } from "@/hooks/use-sources";
import { Plus } from "lucide-react";
import Link from "next/link";

export default function BronzeDashboard() {
  const { data: sourceData, isLoading: sourcesLoading } = useSources();
  const { data: stats, isLoading: statsLoading } = useDashboardStats();

  return (
    <div className="space-y-8">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-text-primary">
            Bronze Sources
          </h1>
          <p className="text-sm text-text-secondary mt-1">
            Manage your data ingestion configurations
          </p>
        </div>
        <Link href="/bronze/new">
          <Button>
            <Plus size={16} />
            Add Source
          </Button>
        </Link>
      </div>

      {/* Stats */}
      <StatsCards stats={stats} loading={statsLoading} />

      {/* Source table */}
      <SourceTable
        sources={sourceData?.sources || []}
        loading={sourcesLoading}
      />
    </div>
  );
}
