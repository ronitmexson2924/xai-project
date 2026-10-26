"use client";

import { motion } from "motion/react";
import React, { useEffect, useState } from "react";

import { AppShell, PageLoading } from "@/components/AppShell";
import { Badge } from "@/components/ui/Badge";
import { Button, ButtonLink, Spinner } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { fadeUp, Stagger } from "@/components/ui/motion";
import { Progress } from "@/components/ui/Progress";
import { AdminMetricsResponse, api } from "@/lib/api";
import { useLearnerGuard } from "@/lib/guards";

const LATENCY_BUDGET_MS = 300; // ARCHITECTURE.md: p95 budget for POST /session/next
type ExportTable = "users" | "assignments" | "attempts";

function ms(value: number | null | undefined): string {
  return value == null ? "—" : value.toFixed(1);
}

function Verdict({ value }: { value: number | null | undefined }) {
  if (value == null) return <Badge>no data yet</Badge>;
  const ok = value < LATENCY_BUDGET_MS;
  return (
    <Badge tone={ok ? "success" : "danger"}>
      {ok ? "within" : "over"} {LATENCY_BUDGET_MS} ms budget
    </Badge>
  );
}

export default function AdminPage() {
  const isAdmin = useLearnerGuard({ requireAdmin: true });
  const [metrics, setMetrics] = useState<AdminMetricsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);

  useEffect(() => {
    if (!isAdmin) return;
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
  }, [isAdmin]);

  const handleDownloadCsv = async (table: ExportTable) => {
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
      setError(err instanceof Error ? err.message : `Failed to download the ${table} export.`);
    } finally {
      setDownloading(null);
    }
  };

  const armDist = metrics?.arm_distribution || {};
  const totalUsers = metrics?.total_users || 0;

  const sourceMix: Record<string, number> = metrics?.source_mix ?? {};
  const totalSources = Object.values(sourceMix).reduce((a, b) => a + b, 0) || 1;

  const clarityDist: Record<string, number> = metrics?.clarity_distribution ?? {};
  const totalRatings = Object.values(clarityDist).reduce((a, b) => a + b, 0) || 1;

  if (!isAdmin) return <PageLoading />;

  const kpis = [
    { label: "Participants", value: String(metrics?.total_users ?? 0), hint: "Balanced randomisation" },
    { label: "Practice attempts", value: String(metrics?.total_attempts ?? 0), hint: "Logged answers" },
    {
      label: "p50 explanation latency",
      value: `${ms(metrics?.p50_explanation_latency_ms)} ms`,
      hint: "Median time to produce an explanation",
      verdict: metrics?.p50_explanation_latency_ms,
    },
    {
      label: "p95 explanation latency",
      value: `${ms(metrics?.p95_explanation_latency_ms)} ms`,
      hint: "95th percentile, all explanations",
      verdict: metrics?.p95_explanation_latency_ms,
    },
  ];
  const arms = [
    { key: "closed_loop", label: "Closed loop", desc: "Traits keep updating from explanation feedback" },
    { key: "static_personalized", label: "Static personalised", desc: "Traits fixed after the questionnaire" },
    { key: "generic", label: "Generic", desc: "Non-personalised explanations (control)" },
  ];
  const sources = [
    { key: "precomputed", label: "Precomputed variants" },
    { key: "template", label: "Deterministic template" },
    { key: "llm", label: "Live grounded LLM" },
  ];
  const exports: { table: ExportTable; title: string; desc: string }[] = [
    { table: "users", title: "Users", desc: "Pseudonymous IDs, signup time, consent status and arm." },
    { table: "assignments", title: "Assignments", desc: "Randomisation events and their timestamps." },
    { table: "attempts", title: "Attempts", desc: "Answers, correctness, latency and timestamps." },
  ];

  return (
    <AppShell wide>
      <Stagger className="space-y-8">
        <motion.div variants={fadeUp} className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
          <div>
            <Badge tone="primary">Research &amp; operations</Badge>
            <h1 className="mt-3 text-2xl font-semibold tracking-tight text-fg sm:text-3xl">Study analytics</h1>
            <p className="mt-1 max-w-2xl text-sm text-muted">
              Arm balance, explanation latency, explanation sources, clarity ratings and pseudonymised exports.
            </p>
          </div>
          <ButtonLink href="/dashboard" variant="secondary">
            Open learner view
          </ButtonLink>
        </motion.div>

        {loading ? (
          <div className="flex flex-col items-center gap-3 py-24 text-sm text-muted" aria-busy>
            <Spinner className="h-6 w-6 text-primary" />
            Loading metrics…
          </div>
        ) : error ? (
          <p role="alert" className="rounded-xl border border-danger/30 bg-danger-soft p-6 text-center text-sm text-danger">
            {error}
          </p>
        ) : (
          <>
            <motion.div variants={fadeUp} className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {kpis.map((k) => (
                <Card key={k.label} className="p-5">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm text-muted">{k.label}</p>
                    {"verdict" in k && <Verdict value={k.verdict} />}
                  </div>
                  <p className="mt-2 text-3xl font-semibold tabular-nums tracking-tight text-fg">{k.value}</p>
                  <p className="mt-1 text-xs text-subtle">{k.hint}</p>
                </Card>
              ))}
            </motion.div>

            <motion.div variants={fadeUp}>
              <Card className="p-6">
                <h2 className="font-semibold text-fg">Participants per study arm</h2>
                <p className="mt-0.5 text-sm text-muted">Balanced randomisation keeps the arms comparable.</p>
                <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-3">
                  {arms.map((arm) => {
                    const count = armDist[arm.key] || 0;
                    const share = totalUsers > 0 ? count / totalUsers : 0;
                    return (
                      <div key={arm.key} className="space-y-3 rounded-xl border border-line bg-surface-2/50 p-4">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium text-fg">{arm.label}</span>
                          <span className="text-sm tabular-nums text-fg">{count}</span>
                        </div>
                        <p className="text-xs text-muted">{arm.desc}</p>
                        <Progress value={share} label={`${arm.label} share`} />
                        <p className="text-right text-xs tabular-nums text-subtle">{Math.round(share * 100)}%</p>
                      </div>
                    );
                  })}
                </div>
              </Card>
            </motion.div>

            <motion.div variants={fadeUp} className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <Card className="p-6">
                <h2 className="font-semibold text-fg">Explanation sources</h2>
                <p className="mt-0.5 text-sm text-muted">Where each explanation shown to a learner came from.</p>
                <div className="mt-5 space-y-4">
                  {sources.map((s) => {
                    const count = sourceMix[s.key] || 0;
                    return (
                      <div key={s.key} className="space-y-1.5">
                        <div className="flex justify-between text-sm">
                          <span className="text-fg">{s.label}</span>
                          <span className="tabular-nums text-muted">
                            {count} ({Math.round((count / totalSources) * 100)}%)
                          </span>
                        </div>
                        <Progress value={count / totalSources} label={s.label} />
                      </div>
                    );
                  })}
                </div>
              </Card>

              <Card className="p-6">
                <h2 className="font-semibold text-fg">Clarity ratings</h2>
                <p className="mt-0.5 text-sm text-muted">Learners&apos; 1-tap ratings, 1 (confusing) to 5 (very clear).</p>
                <div className="mt-5 space-y-2.5">
                  {[5, 4, 3, 2, 1].map((r) => {
                    const count = clarityDist[r] || 0;
                    return (
                      <div key={r} className="flex items-center gap-3 text-sm">
                        <span className="w-4 tabular-nums text-muted">{r}</span>
                        <Progress value={count / totalRatings} label={`Rating ${r}`} tone={r >= 4 ? "success" : "primary"} />
                        <span className="w-16 flex-none text-right tabular-nums text-muted">
                          {count} ({Math.round((count / totalRatings) * 100)}%)
                        </span>
                      </div>
                    );
                  })}
                </div>
              </Card>
            </motion.div>

            <motion.div variants={fadeUp}>
              <Card className="p-6">
                <h2 className="font-semibold text-fg">Research exports</h2>
                <p className="mt-0.5 text-sm text-muted">Pseudonymised CSV tables for the offline analysis.</p>
                <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-3">
                  {exports.map((e) => (
                    <div key={e.table} className="flex flex-col justify-between gap-4 rounded-xl border border-line p-4">
                      <div>
                        <h3 className="text-sm font-medium text-fg">{e.title}</h3>
                        <p className="mt-1 text-xs leading-relaxed text-muted">{e.desc}</p>
                      </div>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => handleDownloadCsv(e.table)}
                        loading={downloading === e.table}
                        aria-label={`Download ${e.table}.csv`}
                      >
                        Download {e.table}.csv
                      </Button>
                    </div>
                  ))}
                </div>
              </Card>
            </motion.div>
          </>
        )}
      </Stagger>
    </AppShell>
  );
}
