"use client";

import { Header } from "@/components/layout/header";
import { Sidebar } from "@/components/layout/sidebar";
import { ToastProvider } from "@/components/ui/toast";

export default function BronzeLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ToastProvider>
      <div className="min-h-screen bg-bg-primary">
        <Sidebar />
        <div className="pl-[240px]">
          <Header />
          <main className="p-8">{children}</main>
        </div>
      </div>
    </ToastProvider>
  );
}
