"use client";

import { useEffect, useMemo, useState } from "react";
import { KeyRound, Trash2, CheckCircle2, AlertCircle, Loader2, Cpu, Database, Plug } from "lucide-react";
import { api } from "@/lib/api";
import type { AccountSettingsResponse, AvailableModel, ProviderKeyStatus } from "@/types";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";

type Provider = "anthropic" | "openai" | "gemini";

const PROVIDER_LABELS: Record<Provider, string> = {
  anthropic: "Anthropic",
  openai: "OpenAI",
  gemini: "Google Gemini",
};

const PROVIDERS: {
  id: Provider;
  label: string;
  description: string;
  placeholder: string;
  docsUrl: string;
  accentClass: string;
}[] = [
  {
    id: "anthropic",
    label: "Anthropic",
    description:
      "Powers the AI Assistant, Silver Modeling advisor, and Test Case Generator. Required for core AI features.",
    placeholder: "sk-ant-api03-...",
    docsUrl: "https://console.anthropic.com/keys",
    accentClass: "border-[#8b7aab]/40 bg-[#8b7aab]/5",
  },
  {
    id: "openai",
    label: "OpenAI",
    description: "Optional — stored for future OpenAI model support.",
    placeholder: "sk-proj-...",
    docsUrl: "https://platform.openai.com/api-keys",
    accentClass: "border-[#5a8a72]/40 bg-[#5a8a72]/5",
  },
  {
    id: "gemini",
    label: "Google Gemini",
    description: "Optional — stored for future Gemini model support.",
    placeholder: "AIzaSy...",
    docsUrl: "https://aistudio.google.com/app/apikey",
    accentClass: "border-[#5b7a9e]/40 bg-[#5b7a9e]/5",
  },
];

function ProviderCard({
  provider,
  status,
  onSaved,
}: {
  provider: (typeof PROVIDERS)[number];
  status: ProviderKeyStatus | null;
  onSaved: (updated: AccountSettingsResponse) => void;
}) {
  const { toast } = useToast();
  const [newKey, setNewKey] = useState("");
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!newKey.trim()) return;
    setSaving(true);
    try {
      const updated = await api.setProviderKey(provider.id, newKey.trim());
      setNewKey("");
      onSaved(updated);
      toast(`${provider.label} API key saved`, "success");
    } catch (err: any) {
      toast(err.message || "Failed to save key", "error");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    setDeleting(true);
    try {
      const updated = await api.deleteProviderKey(provider.id);
      onSaved(updated);
      toast(`${provider.label} API key removed`, "success");
    } catch (err: any) {
      toast(err.message || "Failed to remove key", "error");
    } finally {
      setDeleting(false);
    }
  }

  const configured = status?.configured ?? false;
  const preview = status?.preview ?? null;

  return (
    <div className={`rounded-xl border p-5 ${provider.accentClass}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-1">
        <h3 className="text-sm font-semibold text-text-primary">{provider.label}</h3>
        {configured ? (
          <span className="inline-flex items-center gap-1 text-xs font-medium text-green-600 bg-green-50 border border-green-200 rounded-full px-2 py-0.5">
            <CheckCircle2 size={11} />
            Configured
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 text-xs font-medium text-text-tertiary bg-bg-secondary border border-border rounded-full px-2 py-0.5">
            Not set
          </span>
        )}
      </div>
      <p className="text-xs text-text-secondary mb-4">{provider.description}</p>

      {/* Current key preview + remove */}
      {configured && preview && (
        <div className="flex items-center justify-between bg-bg-card border border-border rounded-lg px-3 py-2 mb-4">
          <span className="text-xs text-text-tertiary font-mono">{preview}</span>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleDelete}
            disabled={deleting}
            className="text-error hover:text-error hover:bg-error/5 h-6 px-2 text-xs"
          >
            {deleting ? <Loader2 size={11} className="animate-spin" /> : <Trash2 size={11} />}
            <span className="ml-1">Remove</span>
          </Button>
        </div>
      )}

      {/* Input */}
      <form onSubmit={handleSave} className="space-y-2">
        <div className="flex gap-2">
          <input
            type="password"
            value={newKey}
            onChange={(e) => setNewKey(e.target.value)}
            placeholder={provider.placeholder}
            className="flex-1 rounded-md border border-border bg-bg-primary px-3 py-2 text-xs
                       text-text-primary placeholder:text-text-tertiary font-mono
                       focus:outline-none focus:ring-1 focus:ring-accent"
          />
          <Button type="submit" size="sm" disabled={saving || !newKey.trim()}>
            {saving ? <Loader2 size={12} className="animate-spin mr-1" /> : null}
            {saving ? "Saving…" : configured ? "Replace" : "Save"}
          </Button>
        </div>
        <p className="text-xs text-text-tertiary">
          Keys are stored server-side and never returned in full.{" "}
          <a
            href={provider.docsUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent hover:underline"
          >
            Get a key →
          </a>
        </p>
      </form>
    </div>
  );
}

function ModelSelector({
  settings,
  models,
  onChanged,
}: {
  settings: AccountSettingsResponse;
  models: AvailableModel[];
  onChanged: (updated: AccountSettingsResponse) => void;
}) {
  const { toast } = useToast();
  const [saving, setSaving] = useState(false);

  const grouped = useMemo(() => {
    const g: Record<Provider, AvailableModel[]> = { anthropic: [], openai: [], gemini: [] };
    for (const m of models) g[m.provider].push(m);
    return g;
  }, [models]);

  async function handleChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const modelId = e.target.value;
    if (modelId === settings.selected_model) return;
    setSaving(true);
    try {
      const updated = await api.setSelectedModel(modelId);
      onChanged(updated);
      toast(`Active model set to ${modelId}`, "success");
    } catch (err: any) {
      toast(err.message || "Failed to update model", "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="bg-bg-card border border-border rounded-xl p-6 mb-6">
      <div className="flex items-center gap-2 mb-1">
        <Cpu size={16} className="text-accent" />
        <h2 className="text-base font-semibold text-text-primary">Active Model</h2>
      </div>
      <p className="text-sm text-text-secondary mb-4">
        Choose which model powers the AI Assistant, Silver Modeling advisor, and
        Test Generator. The matching provider key must be set below.
      </p>
      <div className="flex items-center gap-3">
        <select
          aria-label="Active AI model"
          value={settings.selected_model}
          onChange={handleChange}
          disabled={saving}
          className="flex-1 rounded-md border border-border bg-bg-primary px-3 py-2 text-sm
                     text-text-primary focus:outline-none focus:ring-1 focus:ring-accent"
        >
          {(["anthropic", "openai", "gemini"] as Provider[]).map((provider) =>
            grouped[provider].length > 0 ? (
              <optgroup key={provider} label={PROVIDER_LABELS[provider]}>
                {grouped[provider].map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name} — {m.description}
                  </option>
                ))}
              </optgroup>
            ) : null,
          )}
        </select>
        {saving && <Loader2 size={16} className="animate-spin text-accent" />}
      </div>
      <p className="text-xs text-text-tertiary mt-3">
        Currently active: <span className="font-mono text-text-secondary">{settings.selected_model}</span>
        {" "}(<span className="capitalize">{settings.selected_provider}</span>)
      </p>
    </div>
  );
}

function DatabricksCard({
  settings,
  onChanged,
}: {
  settings: AccountSettingsResponse;
  onChanged: (updated: AccountSettingsResponse) => void;
}) {
  const { toast } = useToast();
  const [host, setHost] = useState("");
  const [token, setToken] = useState("");
  const [warehouseId, setWarehouseId] = useState("");
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string; user?: string | null } | null>(null);

  const status = settings.databricks;
  const configured = status?.configured ?? false;

  const formValid = host.trim().length >= 8 && token.trim().length >= 8 && warehouseId.trim().length >= 4;

  async function handleTest() {
    if (!formValid) return;
    setTesting(true);
    setTestResult(null);
    try {
      const res = await api.testDatabricksConnection({
        host: host.trim(),
        token: token.trim(),
        warehouse_id: warehouseId.trim(),
      });
      setTestResult({ ok: res.ok, message: res.message, user: res.user });
    } catch (err: any) {
      setTestResult({ ok: false, message: err.message || "Test failed" });
    } finally {
      setTesting(false);
    }
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!formValid) return;
    setSaving(true);
    try {
      const updated = await api.setDatabricksCredentials({
        host: host.trim(),
        token: token.trim(),
        warehouse_id: warehouseId.trim(),
      });
      onChanged(updated);
      setHost("");
      setToken("");
      setWarehouseId("");
      setTestResult(null);
      toast("Databricks credentials saved", "success");
    } catch (err: any) {
      toast(err.message || "Failed to save credentials", "error");
    } finally {
      setSaving(false);
    }
  }

  async function handleRemove() {
    setRemoving(true);
    try {
      const updated = await api.deleteDatabricksCredentials();
      onChanged(updated);
      toast("Databricks credentials removed", "success");
    } catch (err: any) {
      toast(err.message || "Failed to remove credentials", "error");
    } finally {
      setRemoving(false);
    }
  }

  return (
    <div className="bg-bg-card border border-border rounded-xl p-6 mb-6">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <Database size={16} className="text-accent" />
          <h2 className="text-base font-semibold text-text-primary">Databricks Workspace</h2>
        </div>
        {configured ? (
          <span className="inline-flex items-center gap-1 text-xs font-medium text-green-600 bg-green-50 border border-green-200 rounded-full px-2 py-0.5">
            <CheckCircle2 size={11} />
            Configured
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 text-xs font-medium text-text-tertiary bg-bg-secondary border border-border rounded-full px-2 py-0.5">
            Not set
          </span>
        )}
      </div>
      <p className="text-sm text-text-secondary mb-4">
        Required for Bronze, Silver, Gold, and Testing pages. Each user supplies their own
        workspace. Credentials are stored server-side and never returned in full.
      </p>

      {configured && status && (
        <div className="bg-bg-secondary border border-border rounded-lg px-3 py-2 mb-4 space-y-1">
          <div className="flex justify-between text-xs">
            <span className="text-text-tertiary">Host</span>
            <span className="font-mono text-text-secondary">{status.host_preview}</span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-text-tertiary">Warehouse ID</span>
            <span className="font-mono text-text-secondary">{status.warehouse_id}</span>
          </div>
          <div className="pt-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleRemove}
              disabled={removing}
              className="text-error hover:text-error hover:bg-error/5 h-6 px-2 text-xs"
            >
              {removing ? <Loader2 size={11} className="animate-spin" /> : <Trash2 size={11} />}
              <span className="ml-1">Remove credentials</span>
            </Button>
          </div>
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-3">
        <div>
          <label className="block text-xs font-medium text-text-secondary mb-1">
            Workspace URL
          </label>
          <input
            type="text"
            value={host}
            onChange={(e) => setHost(e.target.value)}
            placeholder="https://adb-xxxxxxxxxxxxxxxx.x.azuredatabricks.net"
            className="w-full rounded-md border border-border bg-bg-primary px-3 py-2 text-xs
                       text-text-primary placeholder:text-text-tertiary font-mono
                       focus:outline-none focus:ring-1 focus:ring-accent"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-text-secondary mb-1">
            Personal Access Token
          </label>
          <input
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="dapi..."
            className="w-full rounded-md border border-border bg-bg-primary px-3 py-2 text-xs
                       text-text-primary placeholder:text-text-tertiary font-mono
                       focus:outline-none focus:ring-1 focus:ring-accent"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-text-secondary mb-1">
            SQL Warehouse ID
          </label>
          <input
            type="text"
            value={warehouseId}
            onChange={(e) => setWarehouseId(e.target.value)}
            placeholder="abcd1234efgh5678"
            className="w-full rounded-md border border-border bg-bg-primary px-3 py-2 text-xs
                       text-text-primary placeholder:text-text-tertiary font-mono
                       focus:outline-none focus:ring-1 focus:ring-accent"
          />
        </div>

        {testResult && (
          <div
            className={`flex items-start gap-2 rounded-lg px-3 py-2 text-xs ${
              testResult.ok
                ? "bg-green-50 border border-green-200 text-green-700"
                : "bg-error/5 border border-error/20 text-text-secondary"
            }`}
          >
            {testResult.ok ? (
              <CheckCircle2 size={12} className="mt-0.5 shrink-0 text-green-600" />
            ) : (
              <AlertCircle size={12} className="mt-0.5 shrink-0 text-error" />
            )}
            <span>
              {testResult.message}
              {testResult.user ? <> — signed in as <span className="font-mono">{testResult.user}</span></> : null}
            </span>
          </div>
        )}

        <div className="flex gap-2">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={handleTest}
            disabled={!formValid || testing}
          >
            {testing ? <Loader2 size={12} className="animate-spin mr-1" /> : <Plug size={12} className="mr-1" />}
            {testing ? "Testing…" : "Test connection"}
          </Button>
          <Button type="submit" size="sm" disabled={!formValid || saving}>
            {saving ? <Loader2 size={12} className="animate-spin mr-1" /> : null}
            {saving ? "Saving…" : configured ? "Replace" : "Save"}
          </Button>
        </div>
      </form>
    </div>
  );
}

export default function SettingsPage() {
  const { toast } = useToast();
  const [settings, setSettings] = useState<AccountSettingsResponse | null>(null);
  const [models, setModels] = useState<AvailableModel[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.getAccountSettings(), api.listAvailableModels()])
      .then(([s, m]) => {
        setSettings(s);
        setModels(m.models);
      })
      .catch(() => toast("Failed to load settings", "error"))
      .finally(() => setLoading(false));
  }, []);

  // Warning: selected provider has no key
  const selectedProvider = settings?.selected_provider;
  const selectedProviderKeyMissing =
    !!settings && !!selectedProvider && !settings[selectedProvider]?.configured;

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-semibold text-text-primary mb-1">Settings</h1>
      <p className="text-sm text-text-secondary mb-8">Manage your account configuration.</p>

      {loading ? (
        <div className="flex items-center gap-2 text-sm text-text-secondary">
          <Loader2 size={14} className="animate-spin" />
          Loading…
        </div>
      ) : settings ? (
        <>
          {/* Databricks credentials */}
          <DatabricksCard settings={settings} onChanged={setSettings} />

          {/* Active model selector */}
          <ModelSelector settings={settings} models={models} onChanged={setSettings} />

          {/* AI Configuration card */}
          <div className="bg-bg-card border border-border rounded-xl p-6">
            <div className="flex items-center gap-2 mb-1">
              <KeyRound size={16} className="text-accent" />
              <h2 className="text-base font-semibold text-text-primary">AI Provider Keys</h2>
            </div>
            <p className="text-sm text-text-secondary mb-6">
              Add one or more provider keys. Only the key for your Active Model is used at
              request time. Keys are stored server-side and never returned in full.
            </p>

            <div className="space-y-4">
              {PROVIDERS.map((p) => (
                <ProviderCard
                  key={p.id}
                  provider={p}
                  status={settings[p.id] ?? null}
                  onSaved={setSettings}
                />
              ))}
            </div>

            {/* Warning: selected provider missing key */}
            {selectedProviderKeyMissing && selectedProvider && (
              <div className="flex items-start gap-2 mt-5 bg-error/5 border border-error/20 rounded-lg px-4 py-3">
                <AlertCircle size={14} className="text-error mt-0.5 shrink-0" />
                <p className="text-xs text-text-secondary">
                  <span className="font-medium text-text-primary">
                    {PROVIDER_LABELS[selectedProvider]} key required
                  </span>{" "}
                  — your active model ({settings.selected_model}) is a{" "}
                  {PROVIDER_LABELS[selectedProvider]} model, but no{" "}
                  {PROVIDER_LABELS[selectedProvider]} API key is configured. AI features will
                  not work until you add one above, or switch to a different model.
                </p>
              </div>
            )}
          </div>
        </>
      ) : null}
    </div>
  );
}
