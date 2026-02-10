"use client";

import { cn } from "@/lib/utils";
import { useState } from "react";

interface Tab {
  id: string;
  label: string;
  content: React.ReactNode;
}

interface TabsProps {
  tabs: Tab[];
  defaultTab?: string;
  className?: string;
}

export function Tabs({ tabs, defaultTab, className }: TabsProps) {
  const [active, setActive] = useState(defaultTab || tabs[0]?.id);

  return (
    <div className={className}>
      <div className="flex gap-1 border-b border-border">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActive(tab.id)}
            className={cn(
              "px-4 py-2.5 text-sm font-medium transition-colors duration-150 -mb-px",
              "border-b-2 rounded-t-[var(--radius-sm)]",
              active === tab.id
                ? "border-accent text-accent"
                : "border-transparent text-text-secondary hover:text-text-primary hover:border-border-hover"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="pt-5">
        {tabs.find((t) => t.id === active)?.content}
      </div>
    </div>
  );
}
