"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const [checked, setChecked] = useState(false);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    const key = localStorage.getItem("bp_api_key");
    if (!key) {
      router.replace(`/login?from=${encodeURIComponent(pathname)}`);
    } else {
      setChecked(true);
    }
  }, [pathname, router]);

  if (!checked) return null;
  return <>{children}</>;
}
