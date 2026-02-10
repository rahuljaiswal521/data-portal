"use client";

import { Button } from "@/components/ui/button";
import { METADATA_EXPRESSIONS } from "@/lib/constants";
import type { MetadataColumn } from "@/types";
import { Plus, Trash2 } from "lucide-react";

interface MetadataColumnsFieldProps {
  value: MetadataColumn[];
  onChange: (value: MetadataColumn[]) => void;
}

export function MetadataColumnsField({
  value,
  onChange,
}: MetadataColumnsFieldProps) {
  const add = () =>
    onChange([...value, { name: "", expression: "current_timestamp()" }]);
  const remove = (i: number) => onChange(value.filter((_, idx) => idx !== i));
  const update = (i: number, field: keyof MetadataColumn, v: string) =>
    onChange(value.map((col, idx) => (idx === i ? { ...col, [field]: v } : col)));

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-text-primary">
        Metadata Columns
      </label>
      {value.map((col, i) => (
        <div key={i} className="flex gap-2 items-center">
          <input
            type="text"
            value={col.name}
            placeholder="Column name (e.g., _ingest_timestamp)"
            onChange={(e) => update(i, "name", e.target.value)}
            className="w-1/3 rounded-[var(--radius-md)] border border-border bg-bg-card px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
          />
          <select
            value={
              METADATA_EXPRESSIONS.some((e) => e.value === col.expression)
                ? col.expression
                : "__custom__"
            }
            onChange={(e) => {
              if (e.target.value !== "__custom__") {
                update(i, "expression", e.target.value);
              }
            }}
            className="w-1/4 rounded-[var(--radius-md)] border border-border bg-bg-card px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
          >
            {METADATA_EXPRESSIONS.map((expr) => (
              <option key={expr.value} value={expr.value}>
                {expr.label}
              </option>
            ))}
            <option value="__custom__">Custom</option>
          </select>
          <input
            type="text"
            value={col.expression}
            placeholder="Expression"
            onChange={(e) => update(i, "expression", e.target.value)}
            className="flex-1 rounded-[var(--radius-md)] border border-border bg-bg-card px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-accent"
          />
          <button
            type="button"
            onClick={() => remove(i)}
            className="p-1.5 text-text-tertiary hover:text-error transition-colors"
          >
            <Trash2 size={14} />
          </button>
        </div>
      ))}
      <Button type="button" variant="ghost" size="sm" onClick={add}>
        <Plus size={14} /> Add Column
      </Button>
    </div>
  );
}
