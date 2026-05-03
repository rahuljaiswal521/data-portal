"use client";

import { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { Loader2 } from "lucide-react";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const returnTo = searchParams.get("from") || "/bronze";

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!username.trim() || !password.trim()) return;
    setLoading(true);
    setError("");
    try {
      const res = await api.login({ username: username.trim(), password });
      localStorage.setItem("bp_api_key", res.api_key);
      localStorage.setItem("bp_username", res.username);
      if (res.display_name) {
        localStorage.setItem("bp_display_name", res.display_name);
      }
      localStorage.setItem("bp_role", res.role);
      router.replace(returnTo);
    } catch (err: unknown) {
      const e = err as { status?: number; message?: string };
      if (e?.status === 401) {
        setError("Invalid username or password.");
      } else {
        setError("Could not reach the server. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg-primary">
      <div className="w-full max-w-sm">
        {/* Logo / title */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-accent mb-4">
            <span className="text-white text-xl font-bold">D</span>
          </div>
          <h1 className="text-2xl font-semibold text-text-primary">Data Portal</h1>
          <p className="text-sm text-text-secondary mt-1">Sign in to continue</p>
        </div>

        {/* Card */}
        <div className="bg-bg-card border border-border rounded-xl p-8 shadow-sm">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-text-primary mb-1.5">
                Username
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="admin"
                autoComplete="username"
                autoFocus
                className="w-full rounded-md border border-border bg-bg-primary px-3 py-2 text-sm
                           text-text-primary placeholder:text-text-tertiary
                           focus:outline-none focus:ring-1 focus:ring-accent"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-text-primary mb-1.5">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter password"
                autoComplete="current-password"
                className="w-full rounded-md border border-border bg-bg-primary px-3 py-2 text-sm
                           text-text-primary placeholder:text-text-tertiary
                           focus:outline-none focus:ring-1 focus:ring-accent"
              />
            </div>

            {error && (
              <p className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded-md">{error}</p>
            )}

            <Button
              type="submit"
              disabled={loading || !username.trim() || !password.trim()}
              className="w-full"
            >
              {loading ? <Loader2 size={14} className="animate-spin" /> : null}
              {loading ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
