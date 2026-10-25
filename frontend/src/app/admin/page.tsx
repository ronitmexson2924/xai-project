"use client";

import Link from "next/link";
import React, { useEffect, useState } from "react";

import Navbar from "@/components/Navbar";
import { AdminMetricsResponse, api } from "@/lib/api";

export default function AdminPage() {
  const [metrics, setMetrics] = useState<AdminMetricsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    async function loadMetrics() {
      try {
        setLoading(true);
        setError(null);
        const data = await api.admin.getMetrics();
        if (mounted) setMetrics(data);
      } catch (err: unknown) {
        if (mounted) {
          setError(err instanceof Error ? err.message : "Failed to load admin metrics");
        }
      } finally {
        if (mounted) setLoading(false);
      }
    }

    loadMetrics();

    return () => {
      mounted = false;
    };
  }, []);

  const handleDownloadCsv = async (table: string) => {
    try {
      setDownloading(table);
      const blob = await api.admin.downloadCsv(table);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${table}_export.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      console.error(`Export failed for ${table}`, err);
      alert(`Failed to download ${table} CSV export.`);
    } finally {
      setDownloading(null);
    }
  };

  const armDist = metrics?.arm_distribution || {};
  const totalUsers = metrics?.total_users || 0;

  const sourceMix: Record<string, number> = metrics?.source_mix ?? {};
  const totalSources = Object.values(sourceMix).reduce((a, b) => a + b, 0) || 1;

  const clarityDist: Record<number, number> = metrics?.clarity_distribution ?? {};
  const totalRatings = Object.values(clarityDist).reduce((a, b) => a + b, 0) || 1;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <Navbar />

      <main className="flex-1 mx-auto w-full max-w-7xl px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-white/10 pb-6">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                Research &amp; Operations
              </span>
              <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2.5 py-0.5 rounded-full border border-emerald-500/20">
                SLA: &lt; 100ms
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight">
              Study Analytics &amp; Telemetry
            </h1>
            <p className="text-xs sm:text-sm text-slate-400 mt-1 max-w-2xl">
              Real-time monitoring of study arm balancing, p50/p95 latency budgets, explanation source mix, clarity ratings, and pseudonymized research data export.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Link
              href="/dashboard"
              className="px-4 py-2 text-xs font-semibold text-slate-300 hover:text-white bg-slate-900 border border-slate-800 rounded-xl hover:bg-slate-800 transition-colors"
            >
              ← Open Learner Model
            </Link>
          </div>
        </div>

        {loading ? (
          <div className="flex flex-col items-center justify-center py-24 space-y-4">
            <div className="h-10 w-10 animate-spin rounded-full border-4 border-indigo-500 border-t-transparent" />
            <p className="text-xs text-slate-400">Loading operational research metrics...</p>
          </div>
        ) : error ? (
          <div className="rounded-2xl border border-rose-500/30 bg-rose-950/20 p-6 text-center text-rose-300 text-xs">
            {error}
          </div>
        ) : (
          <>
            {/* Top KPIs: Latency SLAs & Totals */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="rounded-3xl border border-white/10 bg-slate-900/60 p-5 backdrop-blur-md">
                <div className="text-[11px] font-medium text-slate-400">Total Participants</div>
                <div className="text-3xl font-black text-white font-mono mt-1">
                  {metrics?.total_users ?? 0}
                </div>
                <div className="text-[10px] text-slate-500 mt-1">Balanced randomisation</div>
              </div>

              <div className="rounded-3xl border border-white/10 bg-slate-900/60 p-5 backdrop-blur-md">
                <div className="text-[11px] font-medium text-slate-400">Total Practice Attempts</div>
                <div className="text-3xl font-black text-emerald-400 font-mono mt-1">
                  {metrics?.total_attempts ?? 0}
                </div>
                <div className="text-[10px] text-slate-500 mt-1">Logged BKT attempts</div>
              </div>

              <div className="rounded-3xl border border-white/10 bg-slate-900/60 p-5 backdrop-blur-md">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-medium text-slate-400">p50 Latency</span>
                  <LatencyBadge value={metrics?.p50_latency_ms ?? null} />
                </div>
                <div className="text-3xl font-black text-cyan-300 font-mono mt-1">
                  {metrics?.p50_latency_ms != null ? metrics.p50_latency_ms.toFixed(1) : "—"} <span className="text-sm font-normal">ms</span>
                </div>
                <div className="text-[10px] text-slate-500 mt-1">Median recommendation latency</div>
              </div>

              <div className="rounded-3xl border border-white/10 bg-slate-900/60 p-5 backdrop-blur-md">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-medium text-slate-400">p95 Latency</span>
                  <LatencyBadge value={metrics?.p95_latency_ms ?? null} />
                </div>
                <div className="text-3xl font-black text-indigo-300 font-mono mt-1">
                  {metrics?.p95_latency_ms != null ? metrics.p95_latency_ms.toFixed(1) : "—"} <span className="text-sm font-normal">ms</span>
                </div>
                <div className="text-[10px] text-slate-500 mt-1">Tail latency constraint (D5)</div>
              </div>
            </div>

            {/* Study Arm Distribution */}
            <section className="rounded-3xl border border-white/10 bg-slate-900/60 p-6 backdrop-blur-md">
              <h2 className="text-sm sm:text-base font-bold text-white mb-1 flex items-center gap-2">
                <span>⚖️</span> Participant Balancing Across Study Arms
              </h2>
              <p className="text-xs text-slate-400 mb-6">
                Online balanced randomisation ensures statistical power across control, static personalization, and closed-loop feedback.
              </p>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {[
                  {
                    key: "closed_loop",
                    label: "Closed Loop (Adaptive)",
                    desc: "Real-time trait feedback from dwell time & clarity ratings",
                    color: "bg-emerald-500",
                    border: "border-emerald-500/40",
                  },
                  {
                    key: "static_personalized",
                    label: "Static Personalized",
                    desc: "Traits fixed from intake survey without explanation updates",
                    color: "bg-indigo-500",
                    border: "border-indigo-500/40",
                  },
                  {
                    key: "generic",
                    label: "Generic Control",
                    desc: "Standard non-personalized baseline explanations",
                    color: "bg-slate-500",
                    border: "border-slate-500/40",
                  },
                ].map((arm) => {
                  const count = armDist[arm.key] || 0;
                  const pct = totalUsers > 0 ? Math.round((count / totalUsers) * 100) : 0;

                  return (
                    <div
                      key={arm.key}
                      className={`rounded-2xl border ${arm.border} bg-slate-950/70 p-4 flex flex-col justify-between`}
                    >
                      <div>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs font-bold text-white">{arm.label}</span>
                          <span className="text-xs font-mono font-black text-white">{count}</span>
                        </div>
                        <p className="text-[11px] text-slate-400 mb-3">{arm.desc}</p>
                      </div>

                      <div className="space-y-1">
                        <div className="flex justify-between text-[10px] text-slate-400 font-mono">
                          <span>Share</span>
                          <span>{pct}%</span>
                        </div>
                        <div className="h-1.5 w-full rounded-full bg-slate-800 overflow-hidden">
                          <div
                            className={`h-full rounded-full ${arm.color}`}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>

            {/* Explanation Telemetry & Source Mix + Clarity Distribution */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Source Mix */}
              <section className="rounded-3xl border border-white/10 bg-slate-900/60 p-6 backdrop-blur-md">
                <h2 className="text-sm sm:text-base font-bold text-white mb-1 flex items-center gap-2">
                  <span>📖</span> Explanation Generation Source Mix
                </h2>
                <p className="text-xs text-slate-400 mb-6">
                  Precomputed variants cached vs live grounded LLM generation vs deterministic fallback.
                </p>

                <div className="space-y-4">
                  {[
                    { key: "precomputed", label: "Precomputed Variants (D6)", color: "bg-emerald-500", count: sourceMix.precomputed || 0 },
                    { key: "template", label: "Deterministic Template", color: "bg-indigo-500", count: sourceMix.template || 0 },
                    { key: "llm", label: "Live Grounded LLM", color: "bg-cyan-500", count: sourceMix.llm || 0 },
                  ].map((s) => {
                    const pct = Math.round((s.count / totalSources) * 100);
                    return (
                      <div key={s.key} className="space-y-1">
                        <div className="flex justify-between text-xs">
                          <span className="font-semibold text-slate-200">{s.label}</span>
                          <span className="font-mono text-slate-300">
                            {s.count} ({pct}%)
                          </span>
                        </div>
                        <div className="h-2 w-full rounded-full bg-slate-800 overflow-hidden">
                          <div className={`h-full rounded-full ${s.color}`} style={{ width: `${pct}%` }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>

              {/* Clarity Rating Distribution */}
              <section className="rounded-3xl border border-white/10 bg-slate-900/60 p-6 backdrop-blur-md">
                <h2 className="text-sm sm:text-base font-bold text-white mb-1 flex items-center gap-2">
                  <span>⭐</span> Explanation Clarity Distribution
                </h2>
                <p className="text-xs text-slate-400 mb-6">
                  Self-reported learner ratings (1 to 5 Likert scale) submitted via formative micro-prompts.
                </p>

                <div className="space-y-2.5">
                  {[5, 4, 3, 2, 1].map((stars) => {
                    const count = clarityDist[stars] || 0;
                    const pct = Math.round((count / totalRatings) * 100);
                    return (
                      <div key={stars} className="flex items-center gap-3 text-xs">
                        <span className="w-12 text-slate-400 font-mono flex items-center gap-1">
                          {stars} ★
                        </span>
                        <div className="h-2 flex-1 rounded-full bg-slate-800 overflow-hidden">
                          <div
                            className={`h-full rounded-full ${
                              stars >= 4
                                ? "bg-emerald-400"
                                : stars === 3
                                ? "bg-amber-400"
                                : "bg-rose-400"
                            }`}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                        <span className="w-14 text-right font-mono text-slate-300">
                          {count} ({pct}%)
                        </span>
                      </div>
                    );
                  })}
                </div>
              </section>
            </div>

            {/* Research Data Export Section */}
            <section className="rounded-3xl border border-white/10 bg-slate-900/60 p-6 backdrop-blur-md">
              <div className="mb-6">
                <h2 className="text-sm sm:text-base font-bold text-white flex items-center gap-2">
                  <span>💾</span> Research Data Exports (CSV)
                </h2>
                <p className="text-xs text-slate-400 mt-1">
                  Download pseudonymized data tables for offline statistical evaluation, Cronbach&apos;s α verification, and Cohen&apos;s κ inter-rater reliability.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
                {[
                  {
                    table: "users",
                    title: "Users Table",
                    desc: "Pseudonymized user IDs, signup timestamp, consent status, and assigned arm.",
                  },
                  {
                    table: "explanations",
                    title: "Explanations Table",
                    desc: "Explanations shown: concept, source (precomputed, LLM, template), style source and latency.",
                  },
                  {
                    table: "feedback",
                    title: "Feedback Table",
                    desc: "Per-explanation feedback: visible dwell, clarity rating, micro-check result, quick dismissal.",
                  },
                  {
                    table: "attempts",
                    title: "Attempts Table",
                    desc: "Item attempts, correctness, latency (ms), confidence ratings, and timestamps.",
                  },
                ].map((item) => (
                  <div
                    key={item.table}
                    className="flex flex-col justify-between rounded-2xl border border-slate-800 bg-slate-950/70 p-5"
                  >
                    <div>
                      <h3 className="text-xs font-bold text-white mb-1">{item.title}</h3>
                      <p className="text-[11px] text-slate-400 leading-relaxed mb-4">
                        {item.desc}
                      </p>
                    </div>

                    <button
                      onClick={() => handleDownloadCsv(item.table)}
                      disabled={downloading === item.table}
                      className="w-full py-2 px-3 text-xs font-bold text-white bg-slate-800 hover:bg-slate-700 rounded-xl transition-colors flex items-center justify-center gap-2 border border-slate-700 disabled:opacity-50"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                      </svg>
                      <span>
                        {downloading === item.table ? "Exporting..." : `Download ${item.table}.csv`}
                      </span>
                    </button>
                  </div>
                ))}
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  );
}

// explainer latency budget: p95 under 50 ms when a precomputed variant exists (tasks/mit.md M3)
function LatencyBadge({ value }: { value: number | null }) {
  if (value == null) {
    return (
      <span className="text-[10px] font-semibold text-slate-400 bg-slate-500/10 px-1.5 py-0.5 rounded border border-slate-500/20">
        no data yet
      </span>
    );
  }
  const ok = value < 50;
  return (
    <span
      className={`text-[10px] font-semibold px-1.5 py-0.5 rounded border ${
        ok
          ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/20"
          : "text-amber-400 bg-amber-500/10 border-amber-500/20"
      }`}
    >
      {ok ? "within budget (<50 ms)" : "over budget (50 ms)"}
    </span>
  );
}
