"use client";

import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { YamlPreview } from "@/components/forms/yaml-preview";
import { CdcBadge, StatusBadge, TypeBadge } from "@/components/sources/status-badge";
import { useDeadLetters, useRunHistory, useSource } from "@/hooks/use-sources";
import { api } from "@/lib/api";
import {
  ArrowLeft,
  Edit,
  Play,
  RotateCw,
  Clock,
  AlertTriangle,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

export default function SourceDetailPage() {
  const params = useParams();
  const name = params.name as string;
  const { data: source, isLoading, mutate } = useSource(name);
  const { data: runs } = useRunHistory(name);
  const { data: deadLetters } = useDeadLetters(name);
  const { toast } = useToast();
  const [triggering, setTriggering] = useState(false);

  const handleTrigger = async () => {
    setTriggering(true);
    try {
      await api.triggerRun(name);
      toast("Run triggered successfully", "success");
    } catch (err: any) {
      toast(err.message || "Failed to trigger run", "error");
    } finally {
      setTriggering(false);
    }
  };

  const handleRedeploy = async () => {
    try {
      await api.deploySource(name);
      toast("Redeployed successfully", "success");
    } catch (err: any) {
      toast(err.message || "Failed to redeploy", "error");
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-80 w-full" />
      </div>
    );
  }

  if (!source) {
    return (
      <div className="text-center py-20">
        <p className="text-text-secondary">Source &apos;{name}&apos; not found</p>
        <Link href="/bronze">
          <Button variant="secondary" className="mt-4">
            <ArrowLeft size={16} /> Back to Dashboard
          </Button>
        </Link>
      </div>
    );
  }

  const configTab = (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {/* General Info */}
      <Card>
        <CardHeader>
          <CardTitle>General</CardTitle>
        </CardHeader>
        <dl className="space-y-3 text-sm">
          <div className="flex justify-between">
            <dt className="text-text-secondary">Name</dt>
            <dd className="font-medium">{source.name}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-text-secondary">Type</dt>
            <dd><TypeBadge type={source.source_type} /></dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-text-secondary">Enabled</dt>
            <dd>
              <Badge variant={source.enabled ? "success" : "default"}>
                {source.enabled ? "Yes" : "No"}
              </Badge>
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-text-secondary">Description</dt>
            <dd className="text-right max-w-[250px]">{source.description || "—"}</dd>
          </div>
          {Object.entries(source.tags).map(([k, v]) => (
            <div key={k} className="flex justify-between">
              <dt className="text-text-secondary">{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
        </dl>
      </Card>

      {/* Connection */}
      {source.connection && Object.keys(source.connection).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Connection</CardTitle>
          </CardHeader>
          <dl className="space-y-3 text-sm">
            {Object.entries(source.connection).map(([k, v]) => {
              if (!v || (typeof v === "object" && Object.keys(v).length === 0)) return null;
              return (
                <div key={k} className="flex justify-between">
                  <dt className="text-text-secondary">{k}</dt>
                  <dd className="font-mono text-xs text-right max-w-[250px] truncate">
                    {typeof v === "object" ? JSON.stringify(v) : String(v)}
                  </dd>
                </div>
              );
            })}
          </dl>
        </Card>
      )}

      {/* Extract */}
      <Card>
        <CardHeader>
          <CardTitle>Extract</CardTitle>
        </CardHeader>
        <dl className="space-y-3 text-sm">
          {Object.entries(source.extract).map(([k, v]) => {
            if (v === null || v === undefined || (typeof v === "object" && Object.keys(v).length === 0)) return null;
            return (
              <div key={k} className="flex justify-between">
                <dt className="text-text-secondary">{k}</dt>
                <dd className="font-mono text-xs text-right max-w-[250px] truncate">
                  {typeof v === "object" ? JSON.stringify(v) : String(v)}
                </dd>
              </div>
            );
          })}
        </dl>
      </Card>

      {/* Target */}
      <Card>
        <CardHeader>
          <CardTitle>Target</CardTitle>
        </CardHeader>
        <dl className="space-y-3 text-sm">
          <div className="flex justify-between">
            <dt className="text-text-secondary">Table</dt>
            <dd className="font-mono text-xs">
              {source.target.catalog}.{source.target.schema}.{source.target.table}
            </dd>
          </div>
          {source.target.cdc && (
            <>
              <div className="flex justify-between">
                <dt className="text-text-secondary">CDC Mode</dt>
                <dd><CdcBadge mode={source.target.cdc.mode || "append"} /></dd>
              </div>
              {source.target.cdc.primary_keys?.length > 0 && (
                <div className="flex justify-between">
                  <dt className="text-text-secondary">Primary Keys</dt>
                  <dd className="font-mono text-xs">
                    {source.target.cdc.primary_keys.join(", ")}
                  </dd>
                </div>
              )}
            </>
          )}
          {source.target.schema_evolution && (
            <div className="flex justify-between">
              <dt className="text-text-secondary">Schema Evolution</dt>
              <dd>{source.target.schema_evolution.mode}</dd>
            </div>
          )}
        </dl>
      </Card>
    </div>
  );

  const yamlTab = <YamlPreview yaml={source.raw_yaml} />;

  const historyTab = (
    <div>
      {runs && runs.runs.length > 0 ? (
        <div className="rounded-[var(--radius-lg)] border border-border overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border bg-bg-secondary/50">
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-text-tertiary">Status</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-text-tertiary">Start Time</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-text-tertiary">Read</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-text-tertiary">Written</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-text-tertiary">Quarantined</th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-text-tertiary">Error</th>
              </tr>
            </thead>
            <tbody>
              {runs.runs.map((run, i) => (
                <tr key={i} className="border-b border-border last:border-0 hover:bg-bg-card-hover transition-colors">
                  <td className="px-4 py-3"><StatusBadge status={run.status} /></td>
                  <td className="px-4 py-3 text-sm text-text-secondary font-mono">{run.start_time || "—"}</td>
                  <td className="px-4 py-3 text-sm text-text-primary">{run.records_read.toLocaleString()}</td>
                  <td className="px-4 py-3 text-sm text-text-primary">{run.records_written.toLocaleString()}</td>
                  <td className="px-4 py-3 text-sm text-text-primary">{run.records_quarantined.toLocaleString()}</td>
                  <td className="px-4 py-3 text-sm text-error max-w-[200px] truncate">{run.error || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="text-center py-12">
          <Clock size={32} className="mx-auto text-text-tertiary mb-3" />
          <p className="text-text-secondary">No run history available</p>
          <p className="text-xs text-text-tertiary mt-1">
            Requires Databricks connection to query audit table
          </p>
        </div>
      )}
    </div>
  );

  const qualityTab = (
    <div>
      {deadLetters && deadLetters.total_count > 0 ? (
        <div>
          <div className="flex items-center gap-3 mb-4">
            <AlertTriangle size={18} className="text-warning" />
            <span className="text-sm font-medium">
              {deadLetters.total_count.toLocaleString()} quarantined records
            </span>
          </div>
          <div className="rounded-[var(--radius-lg)] border border-border overflow-hidden">
            <div className="max-h-[400px] overflow-auto">
              <pre className="p-4 text-xs font-mono text-text-secondary">
                {JSON.stringify(deadLetters.recent_records, null, 2)}
              </pre>
            </div>
          </div>
        </div>
      ) : (
        <div className="text-center py-12">
          <p className="text-text-secondary">No quarantined records</p>
          <p className="text-xs text-text-tertiary mt-1">
            Requires Databricks connection to query dead letter table
          </p>
        </div>
      )}
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link
        href="/bronze"
        className="inline-flex items-center gap-1.5 text-sm text-text-secondary hover:text-text-primary transition-colors"
      >
        <ArrowLeft size={14} /> Back to sources
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold text-text-primary">
            {source.name}
          </h1>
          <TypeBadge type={source.source_type} />
          <Badge variant={source.enabled ? "success" : "default"}>
            {source.enabled ? "Enabled" : "Disabled"}
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={handleRedeploy}
          >
            <RotateCw size={14} /> Redeploy
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={handleTrigger}
            disabled={triggering}
          >
            <Play size={14} /> {triggering ? "Triggering..." : "Trigger Run"}
          </Button>
          <Link href={`/bronze/${name}/edit`}>
            <Button size="sm">
              <Edit size={14} /> Edit
            </Button>
          </Link>
        </div>
      </div>

      {source.description && (
        <p className="text-sm text-text-secondary">{source.description}</p>
      )}

      {/* Tabs */}
      <Tabs
        tabs={[
          { id: "config", label: "Configuration", content: configTab },
          { id: "yaml", label: "Raw YAML", content: yamlTab },
          { id: "history", label: "Run History", content: historyTab },
          { id: "quality", label: "Data Quality", content: qualityTab },
        ]}
      />
    </div>
  );
}
