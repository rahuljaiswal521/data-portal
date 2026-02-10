"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { CdcBadge, EnabledDot, TypeBadge } from "./status-badge";
import type { SourceSummary } from "@/types";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from "@tanstack/react-table";
import { ArrowUpDown, Database, ExternalLink, Search } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

const columnHelper = createColumnHelper<SourceSummary>();

const columns = [
  columnHelper.accessor("enabled", {
    header: "",
    cell: (info) => <EnabledDot enabled={info.getValue()} />,
    size: 32,
  }),
  columnHelper.accessor("name", {
    header: "Name",
    cell: (info) => (
      <Link
        href={`/bronze/${info.getValue()}`}
        className="font-medium text-text-primary hover:text-accent transition-colors"
      >
        {info.getValue()}
      </Link>
    ),
  }),
  columnHelper.accessor("source_type", {
    header: "Type",
    cell: (info) => <TypeBadge type={info.getValue()} />,
  }),
  columnHelper.accessor("target_table", {
    header: "Target Table",
    cell: (info) => (
      <span className="font-mono text-xs text-text-secondary">
        {info.getValue()}
      </span>
    ),
  }),
  columnHelper.accessor("cdc_mode", {
    header: "CDC",
    cell: (info) => <CdcBadge mode={info.getValue()} />,
  }),
  columnHelper.accessor("load_type", {
    header: "Load",
    cell: (info) => (
      <span className="text-sm text-text-secondary capitalize">
        {info.getValue()}
      </span>
    ),
  }),
  columnHelper.accessor("schedule", {
    header: "Schedule",
    cell: (info) => (
      <span className="font-mono text-xs text-text-tertiary">
        {info.getValue() || "Manual"}
      </span>
    ),
  }),
  columnHelper.display({
    id: "actions",
    cell: (info) => (
      <Link href={`/bronze/${info.row.original.name}`}>
        <Button variant="ghost" size="sm">
          <ExternalLink size={14} />
        </Button>
      </Link>
    ),
    size: 48,
  }),
];

interface SourceTableProps {
  sources: SourceSummary[];
  loading: boolean;
}

export function SourceTable({ sources, loading }: SourceTableProps) {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [globalFilter, setGlobalFilter] = useState("");

  const table = useReactTable({
    data: sources,
    columns,
    state: { sorting, globalFilter },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  });

  if (loading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-14 w-full" />
        ))}
      </div>
    );
  }

  return (
    <div>
      {/* Search */}
      <div className="flex items-center gap-3 mb-4">
        <div className="relative flex-1 max-w-sm">
          <Search
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary"
          />
          <input
            type="text"
            placeholder="Search sources..."
            value={globalFilter}
            onChange={(e) => setGlobalFilter(e.target.value)}
            className="w-full rounded-[var(--radius-md)] border border-border bg-bg-card pl-9 pr-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent transition-colors"
          />
        </div>
      </div>

      {/* Table */}
      {sources.length === 0 ? (
        <EmptyState
          icon={<Database size={40} />}
          title="No sources configured"
          description="Get started by adding your first bronze ingestion source."
          action={
            <Link href="/bronze/new">
              <Button>Add First Source</Button>
            </Link>
          }
        />
      ) : (
        <div className="rounded-[var(--radius-lg)] border border-border overflow-hidden">
          <table className="w-full">
            <thead>
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id} className="border-b border-border bg-bg-secondary/50">
                  {hg.headers.map((header) => (
                    <th
                      key={header.id}
                      className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-text-tertiary"
                      style={{ width: header.getSize() !== 150 ? header.getSize() : undefined }}
                    >
                      {header.isPlaceholder ? null : (
                        <button
                          className="flex items-center gap-1 hover:text-text-primary transition-colors"
                          onClick={header.column.getToggleSortingHandler()}
                        >
                          {flexRender(
                            header.column.columnDef.header,
                            header.getContext()
                          )}
                          {header.column.getCanSort() && (
                            <ArrowUpDown size={12} className="opacity-40" />
                          )}
                        </button>
                      )}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  className="border-b border-border last:border-0 hover:bg-bg-card-hover transition-colors"
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-4 py-3">
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
