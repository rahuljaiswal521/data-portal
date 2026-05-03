"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import {
  Database,
  FileText,
  Globe,
  Radio,
  Server,
  Shield,
  GitMerge,
  Layers,
  BarChart2,
  Zap,
  ImageIcon,
  Play,
  CheckCircle2,
} from "lucide-react";

// ─── Design tokens (kept as JS so SVG can reference them) ────────────────────
const C = {
  bg: "#191918",
  bgCard: "#1e1e1c",
  border: "#2e2e2c",
  textDim: "#6b6b65",
  textMid: "#9c9c95",
  bronze: "#d97757",       // portal accent doubles as bronze — warm rust
  bronzeDim: "#7c3c24",
  bronzeBg: "#1f1008",
  silver: "#8fa8c0",
  silverDim: "#3d5a73",
  silverBg: "#0c1218",
  gold: "#c4a43b",
  goldDim: "#6b5615",
  goldBg: "#18140a",
  portal: "#d97757",
  portalDim: "rgba(217,119,87,0.15)",
  src: "#6b7280",
  srcDim: "#374151",
  srcBg: "#111113",
};

// ─── Animated SVG flow diagram ───────────────────────────────────────────────
function FlowDiagram() {
  // Arrow-head paths share the same shape; colour differs per connector
  const ArrowHead = ({ id, fill }: { id: string; fill: string }) => (
    <marker id={id} markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
      <path d="M0,0 L8,3 L0,6 Z" fill={fill} opacity="0.7" />
    </marker>
  );

  // Three animated dots per connector at 0 / 0.8 / 1.6 s offsets
  const FlowDots = ({
    path,
    fill,
    dur = "2.4",
    baseDelay = 0,
  }: {
    path: string;
    fill: string;
    dur?: string;
    baseDelay?: number;
  }) =>
    [0, 0.8, 1.6].map((d, i) => (
      <circle key={i} r="4" fill={fill} opacity="0.9">
        <animateMotion
          dur={`${dur}s`}
          begin={`${baseDelay + d}s`}
          repeatCount="indefinite"
          path={path}
        />
      </circle>
    ));

  const connector = "M 0 0 L 72 0";

  return (
    <div className="w-full rounded-xl overflow-hidden border border-border">
      <svg
        viewBox="0 0 960 310"
        className="w-full"
        style={{ background: C.bg, display: "block" }}
        aria-label="Bronze to Silver to Gold data flow diagram"
      >
        {/* ── Definitions ───────────────────────────────────────────── */}
        <defs>
          <ArrowHead id="arr-bronze" fill={C.bronze} />
          <ArrowHead id="arr-silver" fill={C.silver} />
          <ArrowHead id="arr-gold" fill={C.gold} />
          <filter id="glow-bronze">
            <feGaussianBlur stdDeviation="2" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>

        {/* ── Grid lines (subtle depth) ─────────────────────────────── */}
        {[80, 160, 230].map((y) => (
          <line key={y} x1="0" y1={y} x2="960" y2={y} stroke={C.border} strokeWidth="0.5" strokeOpacity="0.4" />
        ))}

        {/* ══════════════ SOURCES box (x=20) ════════════════════════  */}
        <rect x="20" y="50" width="160" height="170" rx="10" fill={C.srcBg} stroke={C.srcDim} strokeWidth="1.5" />
        {/* header band */}
        <rect x="20" y="50" width="160" height="34" rx="10" fill={C.srcDim} fillOpacity="0.4" />
        <rect x="20" y="72" width="160" height="12" fill={C.srcDim} fillOpacity="0.15" />
        <text x="100" y="72" textAnchor="middle" fill={C.textMid} fontSize="11" fontWeight="700" letterSpacing="1.5">SOURCES</text>
        <line x1="35" y1="93" x2="165" y2="93" stroke={C.border} strokeWidth="0.8" />
        {["Files (CSV, JSON, Parquet)", "REST APIs", "JDBC / Databases", "Kafka Streams", "CDC Events"].map((t, i) => (
          <text key={i} x="100" y={110 + i * 19} textAnchor="middle" fill={C.textDim} fontSize="10">{t}</text>
        ))}

        {/* connector Sources → Bronze */}
        <line x1="180" y1="135" x2="248" y2="135" stroke={C.bronze} strokeWidth="1.5" strokeOpacity="0.4" markerEnd="url(#arr-bronze)" />
        <FlowDots path={`M 180 135 L 248 135`} fill={C.bronze} baseDelay={0} />

        {/* ══════════════ BRONZE box (x=255) ════════════════════════  */}
        <rect x="255" y="30" width="175" height="210" rx="10" fill={C.bronzeBg} stroke={C.bronze} strokeWidth="1.5" strokeOpacity="0.8" />
        <rect x="255" y="30" width="175" height="36" rx="10" fill={C.bronze} fillOpacity="0.2" />
        <rect x="255" y="54" width="175" height="12" fill={C.bronze} fillOpacity="0.1" />
        <text x="342" y="53" textAnchor="middle" fill={C.bronze} fontSize="12" fontWeight="700" letterSpacing="2">BRONZE</text>
        <text x="342" y="67" textAnchor="middle" fill={C.bronzeDim} fontSize="9" letterSpacing="1">RAW INGESTION</text>
        <line x1="272" y1="77" x2="412" y2="77" stroke={C.bronze} strokeWidth="0.5" strokeOpacity="0.3" />
        {["Schema-on-read landing", "SCD2 change tracking", "Dead letter quarantine", "Quality enforcement", "Ingestion audit log", "Multi-format support"].map((t, i) => (
          <text key={i} x="342" y={93 + i * 19} textAnchor="middle" fill="#c4873b" fontSize="10">{t}</text>
        ))}
        {/* portal role badge */}
        <rect x="272" y="212" width="141" height="20" rx="5" fill={C.portal} fillOpacity="0.15" stroke={C.portal} strokeWidth="0.8" strokeOpacity="0.4" />
        <text x="342" y="226" textAnchor="middle" fill={C.portal} fontSize="9" fontWeight="600">Portal: configure &amp; deploy jobs</text>

        {/* connector Bronze → Silver */}
        <line x1="430" y1="135" x2="498" y2="135" stroke={C.silver} strokeWidth="1.5" strokeOpacity="0.4" markerEnd="url(#arr-silver)" />
        <FlowDots path={`M 430 135 L 498 135`} fill={C.silver} baseDelay={0.3} />

        {/* ══════════════ SILVER box (x=505) ════════════════════════  */}
        <rect x="505" y="30" width="175" height="210" rx="10" fill={C.silverBg} stroke={C.silver} strokeWidth="1.5" strokeOpacity="0.8" />
        <rect x="505" y="30" width="175" height="36" rx="10" fill={C.silver} fillOpacity="0.15" />
        <rect x="505" y="54" width="175" height="12" fill={C.silver} fillOpacity="0.08" />
        <text x="592" y="53" textAnchor="middle" fill={C.silver} fontSize="12" fontWeight="700" letterSpacing="2">SILVER</text>
        <text x="592" y="67" textAnchor="middle" fill={C.silverDim} fontSize="9" letterSpacing="1">CANONICAL ENTITIES</text>
        <line x1="522" y1="77" x2="662" y2="77" stroke={C.silver} strokeWidth="0.5" strokeOpacity="0.3" />
        {["3NF business modelling", "Multi-source SCD2 merge", "Domain entity design", "Attribute-level priority", "Quality contracts", "OpenLineage tracking"].map((t, i) => (
          <text key={i} x="592" y={93 + i * 19} textAnchor="middle" fill={C.silver} fontSize="10" fillOpacity="0.85">{t}</text>
        ))}
        <rect x="522" y="212" width="141" height="20" rx="5" fill={C.portal} fillOpacity="0.15" stroke={C.portal} strokeWidth="0.8" strokeOpacity="0.4" />
        <text x="592" y="226" textAnchor="middle" fill={C.portal} fontSize="9" fontWeight="600">Portal: model &amp; transform</text>

        {/* connector Silver → Gold */}
        <line x1="680" y1="135" x2="748" y2="135" stroke={C.gold} strokeWidth="1.5" strokeOpacity="0.4" markerEnd="url(#arr-gold)" />
        <FlowDots path={`M 680 135 L 748 135`} fill={C.gold} baseDelay={0.6} />

        {/* ══════════════ GOLD box (x=755) ════════════════════════  */}
        <rect x="755" y="30" width="175" height="210" rx="10" fill={C.goldBg} stroke={C.gold} strokeWidth="1.5" strokeOpacity="0.5" strokeDasharray="6 3" />
        <rect x="755" y="30" width="175" height="36" rx="10" fill={C.gold} fillOpacity="0.12" />
        <rect x="755" y="54" width="175" height="12" fill={C.gold} fillOpacity="0.06" />
        <text x="842" y="53" textAnchor="middle" fill={C.gold} fontSize="12" fontWeight="700" letterSpacing="2">GOLD</text>
        <text x="842" y="67" textAnchor="middle" fill={C.goldDim} fontSize="9" letterSpacing="1">ANALYTICS READY</text>
        <line x1="772" y1="77" x2="912" y2="77" stroke={C.gold} strokeWidth="0.5" strokeOpacity="0.25" />
        {["Star schema output", "Fact tables", "Dimension tables", "BI & Reporting", "Aggregations", "Data products"].map((t, i) => (
          <text key={i} x="842" y={93 + i * 19} textAnchor="middle" fill={C.gold} fontSize="10" fillOpacity="0.6">{t}</text>
        ))}
        <rect x="772" y="212" width="141" height="20" rx="5" fill={C.gold} fillOpacity="0.12" stroke={C.gold} strokeWidth="0.8" strokeOpacity="0.3" />
        <text x="842" y="226" textAnchor="middle" fill={C.gold} fontSize="9" fontWeight="600" fillOpacity="0.7">Coming soon</text>

        {/* ══════════════ Portal banner (bottom) ═══════════════════  */}
        <rect x="255" y="258" width="675" height="28" rx="7" fill={C.portal} fillOpacity="0.08" stroke={C.portal} strokeWidth="1" strokeOpacity="0.25" />
        <text x="592" y="276" textAnchor="middle" fill={C.portal} fontSize="11" fontWeight="600" letterSpacing="0.3">
          Data Platform Portal — self-service pipeline management across all layers
        </text>
      </svg>
    </div>
  );
}

// ─── Layer detail cards ───────────────────────────────────────────────────────
const LAYER_DETAILS = [
  {
    label: "Bronze Layer",
    sublabel: "Raw ingestion",
    color: "text-[#d97757]",
    border: "border-[#d97757]/30",
    bg: "bg-[#d97757]/5",
    dot: "bg-[#d97757]",
    capabilities: [
      { icon: FileText, text: "Configure file, JDBC, API and streaming sources" },
      { icon: Shield, text: "SCD2 change tracking with surrogate keys" },
      { icon: Database, text: "Dead letter quarantine for bad records" },
      { icon: CheckCircle2, text: "Quality thresholds and quarantine rules" },
      { icon: Server, text: "Ingestion audit log — every run tracked" },
    ],
  },
  {
    label: "Silver Layer",
    sublabel: "Canonical entities",
    color: "text-[#8fa8c0]",
    border: "border-[#8fa8c0]/30",
    bg: "bg-[#8fa8c0]/5",
    dot: "bg-[#8fa8c0]",
    capabilities: [
      { icon: Layers, text: "Design canonical domain entities (3NF)" },
      { icon: GitMerge, text: "Multi-source SCD2 merge with attribute priority" },
      { icon: Globe, text: "AI-assisted entity modelling advisor" },
      { icon: BarChart2, text: "Entity-relationship diagram generation" },
      { icon: Shield, text: "Quality contracts and validation rules" },
    ],
  },
  {
    label: "Gold Layer",
    sublabel: "Coming soon",
    color: "text-[#c4a43b]",
    border: "border-[#c4a43b]/20",
    bg: "bg-[#c4a43b]/5",
    dot: "bg-[#c4a43b]",
    comingSoon: true,
    capabilities: [
      { icon: BarChart2, text: "Star schema design — facts and dimensions" },
      { icon: Zap, text: "Aggregation and rollup pipelines" },
      { icon: Radio, text: "BI tool connectivity (Power BI, Tableau)" },
      { icon: Database, text: "Data product publication" },
      { icon: CheckCircle2, text: "SLA monitoring and freshness checks" },
    ],
  },
];

function LayerCard({
  layer,
}: {
  layer: (typeof LAYER_DETAILS)[number];
}) {
  return (
    <div
      className={cn(
        "rounded-xl border p-5 flex flex-col gap-4",
        layer.bg,
        layer.border,
        layer.comingSoon && "opacity-60"
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className={cn("text-base font-semibold", layer.color)}>
            {layer.label}
          </h3>
          <p className="text-xs text-text-tertiary mt-0.5">{layer.sublabel}</p>
        </div>
        {layer.comingSoon && (
          <span className="text-[10px] font-medium uppercase tracking-wider px-2 py-0.5 rounded-full border border-border text-text-tertiary">
            Soon
          </span>
        )}
      </div>
      <ul className="space-y-2.5">
        {layer.capabilities.map((cap, i) => (
          <li key={i} className="flex items-start gap-2.5">
            <cap.icon size={14} className={cn("mt-0.5 shrink-0", layer.color)} />
            <span className="text-sm text-text-secondary">{cap.text}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ─── GIF view ─────────────────────────────────────────────────────────────────
function GifView() {
  return (
    <div className="rounded-xl border border-border bg-bg-secondary flex flex-col items-center justify-center min-h-[420px] gap-4 p-8">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/architecture-overview.gif"
        alt="Platform architecture overview"
        className="max-w-full rounded-lg"
        onError={(e) => {
          (e.currentTarget as HTMLImageElement).style.display = "none";
          (e.currentTarget.nextElementSibling as HTMLElement | null)?.removeAttribute("hidden");
        }}
      />
      <div hidden className="flex flex-col items-center gap-3 text-center">
        <div className="w-14 h-14 rounded-full bg-bg-card border border-border flex items-center justify-center">
          <ImageIcon size={24} className="text-text-tertiary" />
        </div>
        <div>
          <p className="text-sm font-medium text-text-primary">No GIF uploaded yet</p>
          <p className="text-xs text-text-tertiary mt-1 max-w-xs">
            Drop your file at{" "}
            <code className="bg-bg-card border border-border rounded px-1.5 py-0.5 text-accent font-mono text-[11px]">
              portal/frontend/public/architecture-overview.gif
            </code>{" "}
            and it will appear here automatically.
          </p>
        </div>
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────
type Tab = "diagram" | "gif";

export default function ArchitecturePage() {
  const [tab, setTab] = useState<Tab>("diagram");

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold text-text-primary">
            Platform Architecture
          </h2>
          <p className="text-sm text-text-secondary mt-1">
            How data flows from raw sources through Bronze and Silver to
            analytics-ready Gold
          </p>
        </div>

        {/* Tab toggle */}
        <div className="flex items-center gap-1 p-1 bg-bg-secondary rounded-[var(--radius-md)] border border-border shrink-0">
          <button
            onClick={() => setTab("diagram")}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--radius-sm)] text-sm font-medium transition-colors",
              tab === "diagram"
                ? "bg-bg-card text-text-primary shadow-sm border border-border"
                : "text-text-secondary hover:text-text-primary"
            )}
          >
            <Play size={13} />
            Animated Flow
          </button>
          <button
            onClick={() => setTab("gif")}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--radius-sm)] text-sm font-medium transition-colors",
              tab === "gif"
                ? "bg-bg-card text-text-primary shadow-sm border border-border"
                : "text-text-secondary hover:text-text-primary"
            )}
          >
            <ImageIcon size={13} />
            GIF Overview
          </button>
        </div>
      </div>

      {/* Main diagram / GIF */}
      {tab === "diagram" ? <FlowDiagram /> : <GifView />}

      {/* Layer detail cards */}
      <div>
        <h3 className="text-sm font-semibold text-text-primary mb-3">
          What the Portal does at each layer
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {LAYER_DETAILS.map((layer) => (
            <LayerCard key={layer.label} layer={layer} />
          ))}
        </div>
      </div>
    </div>
  );
}
