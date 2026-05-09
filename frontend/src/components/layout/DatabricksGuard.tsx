"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Database, Settings as SettingsIcon, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";

/**
 * Blocks rendering of Databricks-touching pages until per-tenant
 * Databricks credentials are configured. Shows a friendly prompt linking
 * to Settings if not configured.
 */
export function DatabricksGuard({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<"loading" | "configured" | "missing" | "error">("loading");

  useEffect(() => {
    let active = true;
    api
      .getAccountSettings()
      .then((s) => {
        if (!active) return;
        setState(s.databricks?.configured ? "configured" : "missing");
      })
      .catch(() => {
        if (active) setState("error");
      });
    return () => {
      active = false;
    };
  }, []);

  if (state === "loading") {
    return (
      <div className="flex items-center gap-2 text-sm text-text-secondary">
        <Loader2 size={14} className="animate-spin" />
        Checking Databricks configuration…
      </div>
    );
  }

  if (state === "configured") {
    return <>{children}</>;
  }

  // missing or error → show prompt
  return (
    <div className="max-w-xl mx-auto mt-12">
      <div className="bg-bg-card border border-border rounded-xl p-8 text-center">
        <div className="w-12 h-12 rounded-full bg-accent/10 flex items-center justify-center mx-auto mb-4">
          <Database size={22} className="text-accent" />
        </div>
        <h2 className="text-lg font-semibold text-text-primary mb-2">
          Databricks workspace not configured
        </h2>
        <p className="text-sm text-text-secondary mb-6">
          This page needs your Databricks workspace credentials to read tables, run jobs,
          and query audit logs. Add your workspace URL, personal access token, and SQL
          warehouse ID in Settings to unlock Bronze, Silver, Gold, and Testing.
        </p>
        <Link href="/settings">
          <Button>
            <SettingsIcon size={14} className="mr-2" />
            Open Settings
          </Button>
        </Link>
        {state === "error" && (
          <p className="text-xs text-error mt-4">
            Could not load account settings — please check your connection and try again.
          </p>
        )}
      </div>
    </div>
  );
}
