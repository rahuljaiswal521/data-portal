"use client";

import { Button } from "@/components/ui/button";
import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";

interface KeyValueFieldProps {
  label: string;
  value: Record<string, string>;
  onChange: (value: Record<string, string>) => void;
}

export function KeyValueField({ label, value, onChange }: KeyValueFieldProps) {
  const entries = Object.entries(value);

  const addEntry = () => {
    onChange({ ...value, "": "" });
  };

  const removeEntry = (key: string) => {
    const next = { ...value };
    delete next[key];
    onChange(next);
  };

  const updateKey = (oldKey: string, newKey: string) => {
    const entries = Object.entries(value);
    const updated: Record<string, string> = {};
    for (const [k, v] of entries) {
      updated[k === oldKey ? newKey : k] = v;
    }
    onChange(updated);
  };

  const updateValue = (key: string, newValue: string) => {
    onChange({ ...value, [key]: newValue });
  };

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-text-primary">
        {label}
      </label>
      {entries.map(([k, v], i) => (
        <div key={i} className="flex gap-2 items-center">
          <input
            type="text"
            placeholder="Key"
            value={k}
            onChange={(e) => updateKey(k, e.target.value)}
            className="flex-1 rounded-[var(--radius-md)] border border-border bg-bg-card px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
          />
          <input
            type="text"
            placeholder="Value"
            value={v}
            onChange={(e) => updateValue(k, e.target.value)}
            className="flex-1 rounded-[var(--radius-md)] border border-border bg-bg-card px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
          />
          <button
            type="button"
            onClick={() => removeEntry(k)}
            className="p-1.5 text-text-tertiary hover:text-error transition-colors"
          >
            <Trash2 size={14} />
          </button>
        </div>
      ))}
      <Button type="button" variant="ghost" size="sm" onClick={addEntry}>
        <Plus size={14} /> Add Entry
      </Button>
    </div>
  );
}
