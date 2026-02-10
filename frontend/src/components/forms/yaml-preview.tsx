"use client";

import { Card } from "@/components/ui/card";

interface YamlPreviewProps {
  yaml: string;
}

export function YamlPreview({ yaml }: YamlPreviewProps) {
  return (
    <Card className="bg-bg-dark text-text-inverse p-0 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#2d2d2c]">
        <span className="text-xs font-medium text-text-tertiary">
          Generated YAML
        </span>
        <button
          type="button"
          onClick={() => navigator.clipboard.writeText(yaml)}
          className="text-xs text-text-tertiary hover:text-text-inverse transition-colors"
        >
          Copy
        </button>
      </div>
      <pre className="p-4 text-sm font-mono leading-relaxed overflow-x-auto max-h-[500px] overflow-y-auto text-[#e8e7e0]">
        {yaml}
      </pre>
    </Card>
  );
}
