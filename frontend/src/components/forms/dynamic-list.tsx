"use client";

import { Button } from "@/components/ui/button";
import { Plus, Trash2 } from "lucide-react";

interface DynamicListProps {
  label: string;
  value: string[];
  onChange: (value: string[]) => void;
  placeholder?: string;
}

export function DynamicList({
  label,
  value,
  onChange,
  placeholder = "Enter value",
}: DynamicListProps) {
  const addItem = () => onChange([...value, ""]);
  const removeItem = (i: number) => onChange(value.filter((_, idx) => idx !== i));
  const updateItem = (i: number, v: string) =>
    onChange(value.map((item, idx) => (idx === i ? v : item)));

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-text-primary">
        {label}
      </label>
      {value.map((item, i) => (
        <div key={i} className="flex gap-2 items-center">
          <input
            type="text"
            value={item}
            placeholder={placeholder}
            onChange={(e) => updateItem(i, e.target.value)}
            className="flex-1 rounded-[var(--radius-md)] border border-border bg-bg-card px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
          />
          <button
            type="button"
            onClick={() => removeItem(i)}
            className="p-1.5 text-text-tertiary hover:text-error transition-colors"
          >
            <Trash2 size={14} />
          </button>
        </div>
      ))}
      <Button type="button" variant="ghost" size="sm" onClick={addItem}>
        <Plus size={14} /> Add
      </Button>
    </div>
  );
}
