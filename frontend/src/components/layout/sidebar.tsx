"use client";

import { cn } from "@/lib/utils";
import {
  Database,
  LayoutDashboard,
  Plus,
  Settings,
  Layers,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
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

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed inset-y-0 left-0 z-30 w-[240px] border-r border-border bg-bg-card flex flex-col">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-5 h-16 border-b border-border">
        <div className="flex items-center justify-center w-8 h-8 rounded-[var(--radius-md)] bg-bg-dark">
          <Layers size={16} className="text-text-inverse" />
        </div>
        <div>
          <h1 className="text-[15px] font-semibold text-text-primary leading-tight">
            Data Portal
          </h1>
          <p className="text-[11px] text-text-tertiary leading-tight">
            Lakehouse Platform
          </p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        <p className="px-3 mb-2 text-[11px] font-medium uppercase tracking-wider text-text-tertiary">
          Bronze Layer
        </p>
        {navItems.map((item) => {
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
            Coming Soon
          </p>
          <div className="flex items-center gap-2.5 px-3 py-2 text-sm text-text-tertiary cursor-not-allowed">
            <Database size={16} />
            Silver Layer
          </div>
        </div>
      </nav>

      {/* Footer */}
      <div className="px-3 py-3 border-t border-border">
        <Link
          href="#"
          className="flex items-center gap-2.5 px-3 py-2 rounded-[var(--radius-md)] text-sm text-text-secondary hover:text-text-primary hover:bg-bg-secondary transition-colors"
        >
          <Settings size={16} />
          Settings
        </Link>
      </div>
    </aside>
  );
}
