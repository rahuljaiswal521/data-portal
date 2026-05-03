"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { YamlPreview } from "@/components/forms/yaml-preview";
import { useSilverEntity, useSilverRuns } from "@/hooks/use-silver";
import { api } from "@/lib/api";
import {
  ArrowLeft,
  Clock,
  Pencil,
  PlayCircle,
  RefreshCw,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

function ScdBadge({ type }: { type: string }) {
  return (
    <Badge variant={type === "scd2" ? "accent" : "default"}>
      {type.toUpperCase()}
    </Badge>
  );
}

export default function SilverEntityDetailPage() {
  const params = useParams();
  const router = useRouter();
  const name = params.name as string;
  const { data: entity, isLoading } = useSilverEntity(name);
  const { data: runs } = useSilverRuns(name);
  const { toast } = useToast();
  const [deleting, setDeleting] = useState(false);
  const [deploying, setDeploying] = useState(false);
  const [triggering, setTriggering] = useState(false);

  const handleDeploy = async () => {
    setDeploying(true);
    try {
      const res = await api.deploySilverEntity(name);
      toast(res.message || "Entity deployed successfully", "success");
    } catch (err: any) {
      toast(err.message || "Deploy failed", "error");
    } finally {
      setDeploying(false);
    }
  };

  const handleTrigger = async () => {
    setTriggering(true);
    try {
      const res = await api.triggerSilverRun(name);
      toast(res.message || "Run triggered", "success");
    } catch (err: any) {
      toast(err.message || "Trigger failed", "error");
    } finally {
      setTriggering(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm(`Are you sure you want to delete entity '${name}'?`)) return;
    setDeleting(true);
    try {
      await api.deleteSilverEntity(name);
      toast("Entity deleted successfully", "success");
      router.push("/silver");
    } catch (err: any) {
      toast(err.message || "Failed to delete entity", "error");
    } finally {
      setDeleting(false);
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

  if (!entity) {
    return (
      <div className="text-center py-20">
        <p className="text-text-secondary">
          Entity &apos;{name}&apos; not found
        </p>
        <Link href="/silver">
          <Button variant="secondary" className="mt-4">
            <ArrowLeft size={16} /> Back to Dashboard
          </Button>
        </Link>
      </div>
    );
  }

  const target = entity.target || {};

  // Config tab
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
            <dd className="font-medium">{entity.name}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-text-secondary">Domain</dt>
            <dd className="font-mono text-xs">slv_{entity.domain}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-text-secondary">Enabled</dt>
            <dd>
              <Badge variant={entity.enabled ? "success" : "default"}>
                {entity.enabled ? "Yes" : "No"}
              </Badge>
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-text-secondary">Description</dt>
            <dd className="text-right max-w-[250px]">
              {entity.description || "\u2014"}
            </dd>
          </div>
          {Object.entries(entity.tags).map(([k, v]) => (
            <div key={k} className="flex justify-between">
              <dt className="text-text-secondary">{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
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
              {target.catalog}.{target.schema}.{target.table}
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-text-secondary">SCD Type</dt>
            <dd>
              <ScdBadge type={target.scd_type || "scd2"} />
            </dd>
          </div>
          {target.business_keys?.length > 0 && (
            <div className="flex justify-between">
              <dt className="text-text-secondary">Business Keys</dt>
              <dd className="font-mono text-xs">
                {target.business_keys.join(", ")}
              </dd>
            </div>
          )}
          {target.partition_by?.length > 0 && (
            <div className="flex justify-between">
              <dt className="text-text-secondary">Partition By</dt>
              <dd className="font-mono text-xs">
                {target.partition_by.join(", ")}
              </dd>
            </div>
          )}
        </dl>
      </Card>

      {/* Sources */}
      {entity.sources.map((source: any, idx: number) => (
        <Card key={idx}>
          <CardHeader>
            <CardTitle>
              Source {idx + 1}: {source.bronze_table}
            </CardTitle>
          </CardHeader>
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-text-secondary">Priority</dt>
              <dd>{source.priority ?? 1}</dd>
            </div>
            {source.filter_condition && (
              <div className="flex justify-between">
                <dt className="text-text-secondary">Filter</dt>
                <dd className="font-mono text-xs text-right max-w-[250px] truncate">
                  {source.filter_condition}
                </dd>
              </div>
            )}
            {source.watermark && (
              <div className="flex justify-between">
                <dt className="text-text-secondary">Watermark</dt>
                <dd className="font-mono text-xs">
                  {source.watermark.column} ({source.watermark.type})
                </dd>
              </div>
            )}
            <div>
              <dt className="text-text-secondary mb-2">
                Column Mappings ({source.columns?.length ?? 0})
              </dt>
              <dd>
                <div className="rounded-[var(--radius-md)] border border-border overflow-hidden">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-border bg-bg-secondary/50">
                        <th className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-text-tertiary">
                          Source
                        </th>
                        <th className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-text-tertiary">
                          Target
                        </th>
                        <th className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-text-tertiary">
                          Transform
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {(source.columns || []).map((col: any, ci: number) => (
                        <tr
                          key={ci}
                          className="border-b border-border last:border-0"
                        >
                          <td className="px-3 py-2 font-mono text-xs">
                            {col.source}
                          </td>
                          <td className="px-3 py-2 font-mono text-xs">
                            {col.target}
                          </td>
                          <td className="px-3 py-2 font-mono text-xs text-text-secondary truncate max-w-[200px]">
                            {col.transform || "\u2014"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </dd>
            </div>
          </dl>
        </Card>
      ))}

      {/* Schedule */}
      {entity.schedule && (
        <Card>
          <CardHeader>
            <CardTitle>Schedule</CardTitle>
          </CardHeader>
          <dl className="space-y-3 text-sm">
            {entity.schedule.cron_expression && (
              <div className="flex justify-between">
                <dt className="text-text-secondary">Cron</dt>
                <dd className="font-mono text-xs">
                  {entity.schedule.cron_expression}
                </dd>
              </div>
            )}
            {entity.schedule.timezone && (
              <div className="flex justify-between">
                <dt className="text-text-secondary">Timezone</dt>
                <dd>{entity.schedule.timezone}</dd>
              </div>
            )}
          </dl>
        </Card>
      )}
    </div>
  );

  // YAML tab
  const yamlTab = <YamlPreview yaml={entity.raw_yaml} />;

  // Runs tab
  const runsTab = (
    <div>
      {runs && runs.runs.length > 0 ? (
        <div className="rounded-[var(--radius-lg)] border border-border overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border bg-bg-secondary/50">
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-text-tertiary">
                  Status
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-text-tertiary">
                  Start Time
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-text-tertiary">
                  Read
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-text-tertiary">
                  Written
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-text-tertiary">
                  Skipped
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-text-tertiary">
                  Error
                </th>
              </tr>
            </thead>
            <tbody>
              {runs.runs.map((run, i) => (
                <tr
                  key={i}
                  className="border-b border-border last:border-0 hover:bg-bg-card-hover transition-colors"
                >
                  <td className="px-4 py-3">
                    <Badge
                      variant={
                        run.status === "SUCCESS" ? "success" : "error"
                      }
                    >
                      {run.status}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-sm text-text-secondary font-mono">
                    {run.start_time || "\u2014"}
                  </td>
                  <td className="px-4 py-3 text-sm text-text-primary">
                    {run.records_read.toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-sm text-text-primary">
                    {run.records_written.toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-sm text-text-primary">
                    {run.records_skipped.toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-sm text-error max-w-[200px] truncate">
                    {run.error_message || "\u2014"}
                  </td>
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

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link
        href="/silver"
        className="inline-flex items-center gap-1.5 text-sm text-text-secondary hover:text-text-primary transition-colors"
      >
        <ArrowLeft size={14} /> Back to Silver entities
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold text-text-primary">
            {entity.name}
          </h1>
          <ScdBadge type={target.scd_type || "scd2"} />
          <Badge variant="info">slv_{entity.domain}</Badge>
          <Badge variant={entity.enabled ? "success" : "default"}>
            {entity.enabled ? "Enabled" : "Disabled"}
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          <Link href={`/silver/${name}/edit`}>
            <Button variant="secondary" size="sm">
              <Pencil size={14} /> Edit
            </Button>
          </Link>
          <Button
            variant="secondary"
            size="sm"
            onClick={handleDeploy}
            disabled={deploying}
          >
            <RefreshCw size={14} className={deploying ? "animate-spin" : ""} />
            {deploying ? "Deploying..." : "Deploy"}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={handleTrigger}
            disabled={triggering}
          >
            <PlayCircle size={14} />
            {triggering ? "Triggering..." : "Trigger Run"}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={handleDelete}
            disabled={deleting}
            className="text-error hover:text-error"
          >
            <Trash2 size={14} /> {deleting ? "Deleting..." : "Delete"}
          </Button>
        </div>
      </div>

      {entity.description && (
        <p className="text-sm text-text-secondary">{entity.description}</p>
      )}

      {/* Tabs */}
      <Tabs
        tabs={[
          { id: "config", label: "Configuration", content: configTab },
          { id: "yaml", label: "Raw YAML", content: yamlTab },
          { id: "runs", label: "Run History", content: runsTab },
        ]}
      />
    </div>
  );
}
