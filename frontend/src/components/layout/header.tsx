"use client";

import { usePathname } from "next/navigation";

const titles: Record<string, string> = {
  "/bronze": "Dashboard",
  "/bronze/new": "Add New Source",
};

export function Header() {
  const pathname = usePathname();

  let title = titles[pathname];
  if (!title) {
    if (pathname.endsWith("/edit")) {
      title = "Edit Source";
    } else if (pathname.startsWith("/bronze/")) {
      title = "Source Details";
    }
  }

  return (
    <header className="sticky top-0 z-20 h-16 border-b border-border bg-bg-primary/80 backdrop-blur-md">
      <div className="flex items-center h-full px-8">
        <h2 className="text-lg font-semibold text-text-primary">{title}</h2>
      </div>
    </header>
  );
}
