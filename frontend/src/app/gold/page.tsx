"use client";

import Link from "next/link";
import useSWR from "swr";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { goldApi } from "@/lib/api";
import type { GoldMartSummary } from "@/types/gold";

export default function GoldDashboardPage() {
  const { data, error, isLoading, mutate } = useSWR<GoldMartSummary[]>(
    "gold-marts",
    () => goldApi.listMarts(),
  );

  const onDelete = async (name: string) => {
    if (!confirm(`Delete mart '${name}'? This cannot be undone.`)) return;
    await goldApi.deleteMart(name);
    mutate();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Gold Marts</h1>
          <p className="text-text-secondary mt-1">
            Use-case marts: dimensions, facts, and metrics built from the silver layer.
          </p>
        </div>
        <Link href="/gold/import">
          <Button>Import from Business Rules Sheet</Button>
        </Link>
      </div>

      {error && (
        <Card className="p-4 border-red-300 bg-red-50 text-red-900">
          Failed to load marts: {String(error.message || error)}
        </Card>
      )}

      {isLoading && <Card className="p-6">Loading…</Card>}

      {!isLoading && data && data.length === 0 && (
        <EmptyState
          title="No gold marts yet"
          description="Upload a business-rules workbook to create your first mart."
          action={
            <Link href="/gold/import">
              <Button>Import workbook</Button>
            </Link>
          }
        />
      )}

      {data && data.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {data.map((m) => (
            <Card key={m.name} className="p-5 space-y-2">
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-lg font-semibold">{m.name}</h2>
                  <p className="text-sm text-text-secondary">{m.schema}</p>
                </div>
                <button
                  onClick={() => onDelete(m.name)}
                  className="text-sm text-red-600 hover:underline"
                >
                  Delete
                </button>
              </div>
              {m.description && (
                <p className="text-sm text-text-secondary line-clamp-2">{m.description}</p>
              )}
              <div className="flex gap-4 text-sm pt-2 border-t">
                <span><strong>{m.n_dimensions}</strong> dims</span>
                <span><strong>{m.n_facts}</strong> facts</span>
                <span><strong>{m.n_metrics}</strong> metrics</span>
              </div>
              {m.owner && (
                <p className="text-xs text-text-secondary">Owner: {m.owner}</p>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
