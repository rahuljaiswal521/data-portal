import Image from "next/image";
import Link from "next/link";
import { Layers, ArrowRight, Database, GitMerge, BarChart2 } from "lucide-react";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-bg-dark text-text-inverse flex flex-col">
      {/* ── Nav ──────────────────────────────────────────────────────── */}
      <nav className="flex items-center justify-between px-8 h-16 border-b border-white/10 shrink-0">
        <div className="flex items-center">
          <Image
            src="/ecran-logo.png"
            alt="Ecran"
            width={80}
            height={26}
            className="object-contain invert"
            priority
          />
        </div>
        <Link
          href="/bronze"
          className="flex items-center gap-1.5 px-4 py-1.5 rounded-[var(--radius-md)] bg-accent hover:bg-accent-hover text-white text-sm font-medium transition-colors"
        >
          Get Started
          <ArrowRight size={14} />
        </Link>
      </nav>

      {/* ── Hero ─────────────────────────────────────────────────────── */}
      <section className="flex flex-col items-center text-center px-6 pt-16 pb-10 gap-4">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-accent/30 bg-accent/10 text-accent text-xs font-medium mb-2">
          <Layers size={11} />
          Medallion Architecture
        </div>
        <h1 className="text-4xl sm:text-5xl font-bold text-text-inverse leading-tight max-w-2xl">
          Self-service data pipelines,{" "}
          <span className="text-accent">from source to insight</span>
        </h1>
        <p className="text-base text-white/50 max-w-lg leading-relaxed">
          Configure, deploy and monitor your Bronze → Silver → Gold data
          pipelines without writing a single line of infrastructure code.
        </p>
      </section>

      {/* ── Architecture GIF ─────────────────────────────────────────── */}
      <section className="flex-1 flex items-center justify-center px-6 pb-10">
        <div className="w-full max-w-5xl rounded-2xl overflow-hidden border border-white/10 shadow-2xl">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/architecture-overview.gif"
            alt="Medallion architecture — Bronze to Silver to Gold data flow"
            className="w-full h-auto block"
          />
        </div>
      </section>

      {/* ── CTA ──────────────────────────────────────────────────────── */}
      <section className="flex flex-col items-center gap-3 pb-12 px-6">
        <Link
          href="/bronze"
          className="flex items-center gap-2 px-6 py-3 rounded-[var(--radius-md)] bg-accent hover:bg-accent-hover text-white font-semibold text-base transition-colors shadow-lg"
        >
          Get Started
          <ArrowRight size={16} />
        </Link>
        <Link
          href="/architecture"
          className="text-sm text-white/40 hover:text-white/70 transition-colors"
        >
          View interactive flow diagram →
        </Link>
      </section>

      {/* ── Layer summary cards ───────────────────────────────────────── */}
      <section className="border-t border-white/10 grid grid-cols-1 sm:grid-cols-3 divide-y sm:divide-y-0 sm:divide-x divide-white/10">
        {[
          {
            icon: Database,
            color: "text-[#d97757]",
            label: "Bronze",
            desc: "Ingest raw data from files, APIs, databases and streams with SCD2 tracking and quality quarantine.",
          },
          {
            icon: GitMerge,
            color: "text-[#8fa8c0]",
            label: "Silver",
            desc: "Model canonical business entities with multi-source SCD2 merge, 3NF design and AI-assisted modelling.",
          },
          {
            icon: BarChart2,
            color: "text-[#c4a43b]",
            label: "Gold",
            desc: "Coming soon — analytics-ready star schema, fact/dimension tables and BI-connected data products.",
          },
        ].map(({ icon: Icon, color, label, desc }) => (
          <div key={label} className="flex flex-col gap-2 px-8 py-7">
            <div className="flex items-center gap-2">
              <Icon size={16} className={color} />
              <span className={`text-sm font-semibold ${color}`}>{label}</span>
            </div>
            <p className="text-xs text-white/40 leading-relaxed">{desc}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
