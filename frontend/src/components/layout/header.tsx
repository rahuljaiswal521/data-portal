"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { LogOut, User } from "lucide-react";
import { api } from "@/lib/api";
import { useCurrentUser } from "@/hooks/use-current-user";

const titles: Record<string, string> = {
  "/bronze": "Dashboard",
  "/bronze/new": "Add New Source",
  "/bronze/assistant": "Data Platform Assistant",
};

export function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const { data: user } = useCurrentUser();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  let title = titles[pathname];
  if (!title) {
    if (pathname.endsWith("/edit")) {
      title = "Edit Source";
    } else if (pathname.startsWith("/bronze/")) {
      title = "Source Details";
    }
  }

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  async function handleSignOut() {
    try {
      await api.logout();
    } catch {
      // server-side logout is best-effort; always clear client state
    }
    localStorage.removeItem("bp_api_key");
    localStorage.removeItem("bp_username");
    localStorage.removeItem("bp_display_name");
    localStorage.removeItem("bp_role");
    router.replace("/login");
  }

  const displayName =
    user?.display_name ||
    user?.username ||
    (typeof window !== "undefined"
      ? localStorage.getItem("bp_display_name") ||
        localStorage.getItem("bp_username") ||
        null
      : null);

  const initial = (displayName || "U").trim().charAt(0).toUpperCase();

  return (
    <header className="sticky top-0 z-20 h-16 border-b border-border bg-bg-primary/80 backdrop-blur-md">
      <div className="flex items-center justify-between h-full px-8">
        <h2 className="text-lg font-semibold text-text-primary">{title}</h2>

        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setMenuOpen((v) => !v)}
            className="flex items-center gap-2 px-2 py-1 rounded-md hover:bg-bg-card transition-colors"
            title={displayName || "Account"}
          >
            <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-accent text-white text-xs font-semibold">
              {initial}
            </span>
            <span className="hidden sm:inline text-sm text-text-primary">
              {displayName || "Account"}
            </span>
          </button>

          {menuOpen && (
            <div className="absolute right-0 mt-2 w-56 rounded-lg border border-border bg-bg-card shadow-lg py-1 text-sm">
              <div className="px-3 py-2 border-b border-border">
                <div className="flex items-center gap-2 text-text-primary">
                  <User size={14} />
                  <span className="font-medium truncate">
                    {displayName || "Account"}
                  </span>
                </div>
                {user?.role && (
                  <div className="text-xs text-text-tertiary mt-0.5 capitalize">
                    {user.role}
                  </div>
                )}
              </div>
              <button
                onClick={handleSignOut}
                className="w-full flex items-center gap-2 px-3 py-2 text-text-secondary hover:bg-bg-primary hover:text-text-primary transition-colors text-left"
              >
                <LogOut size={14} />
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
