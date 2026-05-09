"use client";

import { AuthGuard } from "@/components/layout/AuthGuard";
import { DatabricksGuard } from "@/components/layout/DatabricksGuard";
import { Header } from "@/components/layout/header";
import { Sidebar } from "@/components/layout/sidebar";
import { ToastProvider } from "@/components/ui/toast";

export default function TestingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthGuard>
      <ToastProvider>
        <div className="min-h-screen bg-bg-primary">
          <Sidebar />
          <div className="pl-[240px]">
            <Header />
            <main className="p-8">
              <DatabricksGuard>{children}</DatabricksGuard>
            </main>
          </div>
        </div>
      </ToastProvider>
    </AuthGuard>
  );
}
