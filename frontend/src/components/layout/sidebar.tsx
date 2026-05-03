"use client";

import { cn } from "@/lib/utils";
import {
  FileSpreadsheet,
  FlaskConical,
  GitBranch,
  LayoutDashboard,
  MessageSquare,
  Plus,
  Settings,
  Sparkles,
  Workflow,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";

const bronzeItems = [
  {
    label: "Dashboard",
    href: "/bronze",
    icon: LayoutDashboard,
  },
  {
    label: "Add Source",
    href: "/bronze/new",
    icon: Plus,
  },
];

const silverItems = [
  {
    label: "Dashboard",
    href: "/silver",
    icon: LayoutDashboard,
  },
  {
    label: "Model Advisor",
    href: "/silver/model-advisor",
    icon: Sparkles,
  },
  {
    label: "New Entity",
    href: "/silver/new",
    icon: Plus,
  },
  {
    label: "Model Diagram",
    href: "/silver/diagram",
    icon: GitBranch,
  },
];

const goldItems = [
  {
    label: "Dashboard",
    href: "/gold",
    icon: LayoutDashboard,
  },
  {
    label: "Import Workbook",
    href: "/gold/import",
    icon: FileSpreadsheet,
  },
];

const testingItems = [
  {
    label: "Bronze Tests",
    href: "/testing/bronze",
    icon: FlaskConical,
  },
];

const platformItems = [
  {
    label: "Architecture",
    href: "/architecture",
    icon: Workflow,
  },
  {
    label: "AI Assistant",
    href: "/bronze/assistant",
    icon: MessageSquare,
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed inset-y-0 left-0 z-30 w-[240px] border-r border-border bg-bg-sidebar flex flex-col">
      {/* Logo */}
      <div className="flex items-center justify-center px-4 h-16 border-b border-border">
        <Image
          src="/ecran-logo.png"
          alt="Ecran"
          width={150}
          height={48}
          className="object-contain"
          priority
        />
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        <p className="px-3 mb-2 text-[11px] font-medium uppercase tracking-wider text-text-tertiary">
          Bronze Layer
        </p>
        {bronzeItems.map((item) => {
          const isActive =
            item.href === "/bronze"
              ? pathname === "/bronze"
              : pathname.startsWith(item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-2.5 px-3 py-2 rounded-[var(--radius-md)] text-sm font-medium",
                "transition-colors duration-150",
                isActive
                  ? "bg-accent-light text-accent"
                  : "text-text-secondary hover:text-text-primary hover:bg-bg-secondary"
              )}
            >
              <item.icon size={16} />
              {item.label}
            </Link>
          );
        })}

        <div className="pt-6">
          <p className="px-3 mb-2 text-[11px] font-medium uppercase tracking-wider text-text-tertiary">
            Silver Layer
          </p>
          {silverItems.map((item) => {
            const isActive =
              item.href === "/silver"
                ? pathname === "/silver"
                : pathname.startsWith(item.href);

            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-2.5 px-3 py-2 rounded-[var(--radius-md)] text-sm font-medium",
                  "transition-colors duration-150",
                  isActive
                    ? "bg-accent-light text-accent"
                    : "text-text-secondary hover:text-text-primary hover:bg-bg-secondary"
                )}
              >
                <item.icon size={16} />
                {item.label}
              </Link>
            );
          })}
        </div>

        <div className="pt-6">
          <p className="px-3 mb-2 text-[11px] font-medium uppercase tracking-wider text-text-tertiary">
            Gold Layer
          </p>
          {goldItems.map((item) => {
            const isActive =
              item.href === "/gold"
                ? pathname === "/gold"
                : pathname.startsWith(item.href);

            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-2.5 px-3 py-2 rounded-[var(--radius-md)] text-sm font-medium",
                  "transition-colors duration-150",
                  isActive
                    ? "bg-accent-light text-accent"
                    : "text-text-secondary hover:text-text-primary hover:bg-bg-secondary"
                )}
              >
                <item.icon size={16} />
                {item.label}
              </Link>
            );
          })}
        </div>

        <div className="pt-6">
          <p className="px-3 mb-2 text-[11px] font-medium uppercase tracking-wider text-text-tertiary">
            Testing
          </p>
          {testingItems.map((item) => {
            const isActive = pathname.startsWith(item.href);

            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-2.5 px-3 py-2 rounded-[var(--radius-md)] text-sm font-medium",
                  "transition-colors duration-150",
                  isActive
                    ? "bg-accent-light text-accent"
                    : "text-text-secondary hover:text-text-primary hover:bg-bg-secondary"
                )}
              >
                <item.icon size={16} />
                {item.label}
              </Link>
            );
          })}
          <div className="flex items-center gap-2.5 px-3 py-2 text-sm text-text-tertiary cursor-not-allowed">
            <FlaskConical size={16} />
            Silver Tests
            <span className="ml-auto text-[10px] uppercase tracking-wide text-text-tertiary/60">
              soon
            </span>
          </div>
        </div>

        <div className="pt-6">
          <p className="px-3 mb-2 text-[11px] font-medium uppercase tracking-wider text-text-tertiary">
            Platform
          </p>
          {platformItems.map((item) => {
            const isActive = pathname.startsWith(item.href);

            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-2.5 px-3 py-2 rounded-[var(--radius-md)] text-sm font-medium",
                  "transition-colors duration-150",
                  isActive
                    ? "bg-accent-light text-accent"
                    : "text-text-secondary hover:text-text-primary hover:bg-bg-secondary"
                )}
              >
                <item.icon size={16} />
                {item.label}
              </Link>
            );
          })}
        </div>
      </nav>

      {/* Footer */}
      <div className="px-3 py-3 border-t border-border">
        <Link
          href="/settings"
          className="flex items-center gap-2.5 px-3 py-2 rounded-[var(--radius-md)] text-sm text-text-secondary hover:text-text-primary hover:bg-bg-secondary transition-colors"
        >
          <Settings size={16} />
          Settings
        </Link>
      </div>
    </aside>
  );
}
