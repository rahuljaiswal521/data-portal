"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import type { TcConfirmResponse, TcGeneratePreview } from "@/types/testing";
import {
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Loader2,
  RotateCcw,
  Sparkles,
  XCircle,
} from "lucide-react";
import { useState } from "react";

type State = "idle" | "generating" | "preview" | "adding" | "done";

interface Props {
  sourceName: string;
  onTcAdded: () => void;
}

export function AiTcGenerator({ sourceName, onTcAdded }: Props) {
  const { toast } = useToast();
  const [state, setState] = useState<State>("idle");
  const [prompt, setPrompt] = useState("");
  const [preview, setPreview] = useState<TcGeneratePreview | null>(null);
  const [confirmResult, setConfirmResult] = useState<TcConfirmResponse | null>(null);
  const [showRecords, setShowRecords] = useState(false);

  async function handleGenerate() {
    if (!prompt.trim()) return;
    setState("generating");
    try {
      const result = await api.aiGenerateTc(sourceName, prompt.trim());
      setPreview(result);
      setShowRecords(false);
      setState("preview");
    } catch (err: any) {
      toast(err.message || "AI generation failed", "error");
      setState("idle");
    }
  }

  async function handleConfirm() {
    if (!preview) return;
    setState("adding");
    try {
      const result = await api.aiConfirmTc(sourceName, preview);
      setConfirmResult(result);
      setState("done");
      onTcAdded();
      toast(
        result.result.status === "PASSED"
          ? `${result.tc_id} added and passed!`
          : `${result.tc_id} added — check results`,
        result.result.status === "PASSED" ? "success" : "error"
      );
    } catch (err: any) {
      toast(err.message || "Failed to add test case", "error");
      setState("preview");
    }
  }

  function handleReset() {
    setState("idle");
    setPrompt("");
    setPreview(null);
    setConfirmResult(null);
    setShowRecords(false);
  }

  return (
    <Card className="p-5">
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <Sparkles size={16} className="text-accent" />
        <h3 className="text-sm font-semibold text-text-primary">
          Generate a test case with AI
        </h3>
      </div>

      {/* ── IDLE / GENERATING: show input ── */}
      {(state === "idle" || state === "generating") && (
        <div className="space-y-3">
          <p className="text-xs text-text-secondary">
            Describe what you want to test in plain English. The AI will create a
            formal test case, generate test data, and add it to this suite.
          </p>
          <textarea
            className="w-full rounded-md border border-border bg-bg-card px-3 py-2 text-sm
                       text-text-primary placeholder:text-text-tertiary resize-none
                       focus:outline-none focus:ring-1 focus:ring-accent disabled:opacity-50"
            rows={3}
            placeholder='e.g. "Make sure the status column only has values: active, inactive, or pending"'
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            disabled={state === "generating"}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleGenerate();
            }}
          />
          <div className="flex items-center gap-2">
            <Button
              onClick={handleGenerate}
              disabled={state === "generating" || !prompt.trim()}
              size="sm"
            >
              {state === "generating" ? (
                <Loader2 size={13} className="animate-spin" />
              ) : (
                <Sparkles size={13} />
              )}
              {state === "generating" ? "Generating…" : "Generate TC"}
            </Button>
            <span className="text-xs text-text-tertiary">Ctrl+Enter to submit</span>
          </div>
        </div>
      )}

      {/* ── PREVIEW: show generated TC ── */}
      {(state === "preview" || state === "adding") && preview && (
        <div className="space-y-4">
          {/* TC header */}
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-mono text-xs font-semibold text-accent">
                  {preview.tc_id}
                </span>
                <span className="text-xs bg-bg-secondary px-1.5 py-0.5 rounded text-text-secondary capitalize">
                  {preview.category.replace("_", " ")}
                </span>
                <span
                  className={`text-xs font-medium ${
                    preview.positive ? "text-green-600" : "text-orange-500"
                  }`}
                >
                  {preview.positive ? "Positive" : "Negative"}
                </span>
              </div>
              <p className="text-sm font-medium text-text-primary mt-1">
                {preview.name}
              </p>
            </div>
            <button
              onClick={handleReset}
              disabled={state === "adding"}
              className="flex items-center gap-1 text-xs text-text-tertiary hover:text-text-secondary shrink-0"
            >
              <RotateCcw size={11} />
              Try again
            </button>
          </div>

          {/* Explanation */}
          {preview.explanation && (
            <p className="text-xs text-text-secondary bg-bg-secondary rounded px-3 py-2 leading-relaxed">
              {preview.explanation}
            </p>
          )}

          {/* Assertions */}
          <div>
            <p className="text-xs font-medium text-text-secondary mb-1.5">
              Assertions ({preview.assertions.length})
            </p>
            <div className="space-y-1.5">
              {preview.assertions.map((a, i) => (
                <div
                  key={i}
                  className="text-xs bg-bg-secondary rounded px-3 py-2 font-mono text-text-secondary"
                >
                  <span className="text-accent mr-1">{a.type}</span>
                  <span className="text-text-tertiary mr-1">expected</span>
                  <span className="font-semibold text-text-primary">{String(a.expected)}</span>
                  <span className="text-text-tertiary ml-2">— {a.description}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Data records collapsible */}
          <div>
            <button
              className="flex items-center gap-1.5 text-xs font-medium text-text-secondary hover:text-text-primary"
              onClick={() => setShowRecords((v) => !v)}
            >
              {showRecords ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              Test data ({preview.data_records.length} records)
            </button>
            {showRecords && (
              <div className="mt-2 rounded border border-border bg-bg-secondary p-3 overflow-x-auto">
                <pre className="text-xs text-text-secondary whitespace-pre-wrap">
                  {preview.data_records
                    .slice(0, 8)
                    .map((r) => JSON.stringify(r))
                    .join("\n")}
                  {preview.data_records.length > 8 && (
                    `\n… and ${preview.data_records.length - 8} more`
                  )}
                </pre>
              </div>
            )}
          </div>

          {/* Add & Run button */}
          <div className="flex items-center gap-3 pt-1 border-t border-border">
            <Button
              onClick={handleConfirm}
              disabled={state === "adding"}
            >
              {state === "adding" ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <CheckCircle2 size={14} />
              )}
              {state === "adding" ? "Adding & running…" : "Add & Run"}
            </Button>
            <p className="text-xs text-text-tertiary">
              Adds to suite permanently and executes once.
            </p>
          </div>
        </div>
      )}

      {/* ── DONE: show result ── */}
      {state === "done" && confirmResult && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            {confirmResult.result.status === "PASSED" ? (
              <CheckCircle2 size={16} className="text-green-600" />
            ) : (
              <XCircle size={16} className="text-red-500" />
            )}
            <span className="text-sm font-medium text-text-primary">
              {confirmResult.tc_id} added and executed —{" "}
              <span
                className={
                  confirmResult.result.status === "PASSED"
                    ? "text-green-600"
                    : "text-red-500"
                }
              >
                {confirmResult.result.status}
              </span>
            </span>
          </div>
          {confirmResult.result.error && (
            <p className="text-xs text-red-600 font-mono bg-red-50 rounded px-3 py-2">
              {confirmResult.result.error}
            </p>
          )}
          <Button variant="secondary" size="sm" onClick={handleReset}>
            <Sparkles size={13} />
            Generate another
          </Button>
        </div>
      )}
    </Card>
  );
}
