"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useSilverDiagram } from "@/hooks/use-silver";
import { Database, Download, FolderOpen, Layers, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

function DiagramStatsBar({
  entityCount,
  domains,
}: {
  entityCount: number;
  domains: string[];
}) {
  return (
    <div className="flex items-center gap-6 px-4 py-3 bg-bg-card border border-border rounded-[var(--radius-md)]">
      <div className="flex items-center gap-2">
        <Layers size={16} className="text-text-tertiary" />
        <span className="text-sm text-text-secondary">Entities:</span>
        <span className="text-sm font-semibold text-text-primary">
          {entityCount}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <FolderOpen size={16} className="text-text-tertiary" />
        <span className="text-sm text-text-secondary">Domains:</span>
        <div className="flex gap-1.5">
          {domains.map((d) => (
            <Badge key={d} variant="accent">
              {d}
            </Badge>
          ))}
        </div>
      </div>
    </div>
  );
}

function MermaidDiagram({ chart }: { chart: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [svgContent, setSvgContent] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function renderChart() {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({
          startOnLoad: false,
          theme: "neutral",
          er: {
            useMaxWidth: false,
            layoutDirection: "TB",
          },
          securityLevel: "loose",
        });

        const id = `mermaid-${Date.now()}`;
        const { svg } = await mermaid.render(id, chart);
        if (!cancelled) {
          setSvgContent(svg);
          setError(null);
        }
      } catch (e: any) {
        if (!cancelled) {
          setError(e.message || "Failed to render diagram");
          setSvgContent("");
        }
      }
    }

    renderChart();
    return () => {
      cancelled = true;
    };
  }, [chart]);

  const handleDownloadSvg = useCallback(() => {
    if (!svgContent) return;
    const blob = new Blob([svgContent], { type: "image/svg+xml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "silver-model-diagram.svg";
    a.click();
    URL.revokeObjectURL(url);
  }, [svgContent]);

  if (error) {
    return (
      <div className="p-6 bg-[rgba(196,75,59,0.1)] border border-error rounded-[var(--radius-md)]">
        <p className="text-sm text-error font-medium">Diagram render error</p>
        <pre className="mt-2 text-xs text-text-secondary whitespace-pre-wrap">
          {error}
        </pre>
      </div>
    );
  }

  if (!svgContent) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex items-center gap-2 text-text-secondary">
          <RefreshCw size={16} className="animate-spin" />
          <span className="text-sm">Rendering diagram...</span>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex justify-end mb-3">
        <Button variant="secondary" onClick={handleDownloadSvg}>
          <Download size={14} />
          Export SVG
        </Button>
      </div>
      <div
        ref={containerRef}
        className="overflow-auto border border-border rounded-[var(--radius-md)] bg-white p-6"
        dangerouslySetInnerHTML={{ __html: svgContent }}
      />
    </div>
  );
}

export default function SilverDiagramPage() {
  const { data, isLoading, mutate } = useSilverDiagram();

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <Skeleton className="h-7 w-48 mb-2" />
            <Skeleton className="h-4 w-72" />
          </div>
        </div>
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-[500px] w-full" />
      </div>
    );
  }

  if (!data || data.entity_count === 0) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold text-text-primary">
            Model Diagram
          </h2>
          <p className="text-sm text-text-secondary mt-1">
            Entity-relationship diagram of your Silver layer model
          </p>
        </div>
        <EmptyState
          icon={<Database size={40} />}
          title="No Silver entities configured yet"
          description="Create your first Silver entity to see the model diagram."
          action={
            <Link href="/silver/new">
              <Button>Create Entity</Button>
            </Link>
          }
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-text-primary">
            Model Diagram
          </h2>
          <p className="text-sm text-text-secondary mt-1">
            Entity-relationship diagram of your Silver layer model
          </p>
        </div>
        <Button variant="secondary" onClick={() => mutate()}>
          <RefreshCw size={14} />
          Refresh
        </Button>
      </div>

      <DiagramStatsBar
        entityCount={data.entity_count}
        domains={data.domains}
      />

      <MermaidDiagram chart={data.mermaid} />
    </div>
  );
}
