"use client";

import Link from "next/link";
import { motion } from "motion/react";
import React, { useEffect, useMemo, useState } from "react";
import { AppShell, PageLoading } from "@/components/AppShell";
import { MasteryMap } from "@/components/MasteryMap";
import TraitCard from "@/components/TraitCard";
import { ButtonLink } from "@/components/ui/Button";
import { Card, SectionTitle } from "@/components/ui/Card";
import { fadeUp, Stagger } from "@/components/ui/motion";
import { api, Concept, LearnerState, StateUpdateView, TestOut } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useLearnerGuard } from "@/lib/guards";
import { MASTERED } from "@/lib/mastery";

interface Data {
  state: LearnerState;
  concepts: Concept[];
  history: StateUpdateView[];
  pretest: TestOut | null;
  posttest: TestOut | null;
}

function greeting(): string {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

export default function DashboardPage() {
  const ready = useLearnerGuard();
  const { user } = useAuth();
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ready) return;
    Promise.all([
      api.learners.getState(),
      api.graph.get(),
      api.learners.getHistory(30),
      api.tests.get("pretest").catch(() => null),
      api.tests.get("posttest").catch(() => null),
    ])
      .then(([state, graph, history, pretest, posttest]) =>
        setData({ state, concepts: graph.concepts, history, pretest, posttest })
      )
      .catch(() => setError("Could not load your dashboard. Check your connection and refresh."));
  }, [ready]);

  const names = useMemo(() => Object.fromEntries((data?.concepts ?? []).map((c) => [c.id, c.name])), [data]);

  if (!ready) return <PageLoading />;
  const first = (user?.display_name ?? "").split(" ")[0];

  return (
    <AppShell>
      <Stagger className="space-y-10" gap={0.07}>
        <motion.div variants={fadeUp}>
          <h1 className="text-2xl font-semibold tracking-tight text-fg sm:text-3xl">
            {greeting()}
            {first ? `, ${first}` : ""}
          </h1>
          <p className="mt-1 text-muted">Here is where you are, and what is next.</p>
        </motion.div>

        {error && (
          <p role="alert" className="rounded-xl border border-danger/30 bg-danger-soft p-4 text-sm text-danger">
            {error}
          </p>
        )}

        {!data && !error && (
          <div className="grid gap-4 sm:grid-cols-3" aria-busy>
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-28 animate-pulse rounded-xl bg-surface-2" />
            ))}
          </div>
        )}

        {data && (
          <>
            <motion.div variants={fadeUp}>
              <NextStep data={data} />
            </motion.div>
            <motion.div variants={fadeUp}>
              <Stats state={data.state} total={data.concepts.length} />
            </motion.div>
            <motion.div variants={fadeUp}>
              <MasteryMap concepts={data.concepts} state={data.state} />
            </motion.div>
            <motion.div variants={fadeUp}>
              <TraitCard traits={data.state.traits} />
            </motion.div>
            <motion.div variants={fadeUp}>
              <Activity history={data.history} names={names} />
            </motion.div>
          </>
        )}
      </Stagger>
    </AppShell>
  );
}

function NextStep({ data }: { data: Data }) {
  const pretestOpen = data.pretest && data.pretest.items.length > 0 && !data.pretest.submitted;
  const answered = data.state.total_attempts;
  const step = pretestOpen
    ? {
        eyebrow: "Step 1 of the study",
        title: "Take the pre-test",
        body: `${data.pretest!.items.length} questions, about 10 minutes, taken once. There is no score: it measures where you start so the study can see how much you learn.`,
        href: "/tests/pretest",
        cta: "Start the pre-test",
      }
    : answered === 0
      ? {
          eyebrow: "Ready when you are",
          title: "Start learning",
          body: "The first few questions find your level. After that, each step comes with an explanation written for you.",
          href: "/session",
          cta: "Start",
        }
      : {
          eyebrow: "Pick up where you left off",
          title: "Continue learning",
          body: `You have answered ${answered} question${answered === 1 ? "" : "s"}. Your next step is chosen from what you know now.`,
          href: "/session",
          cta: "Continue",
        };

  return (
    <Card className="relative overflow-hidden p-6 sm:p-8" data-testid="next-step">
      <div aria-hidden className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full bg-primary/10 blur-3xl" />
      <p className="text-xs font-medium uppercase tracking-wide text-primary">{step.eyebrow}</p>
      <h2 className="mt-2 text-2xl font-semibold tracking-tight text-fg">{step.title}</h2>
      <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted">{step.body}</p>
      <div className="mt-6 flex flex-wrap items-center gap-3">
        <ButtonLink href={step.href} size="lg">
          {step.cta} <span aria-hidden>→</span>
        </ButtonLink>
        {!pretestOpen && data.posttest && !data.posttest.submitted && data.posttest.items.length > 0 && (
          <Link href="/tests/posttest" className="text-sm text-muted hover:text-fg">
            At the end of the study: take the post-test
          </Link>
        )}
      </div>
    </Card>
  );
}

function Stats({ state, total }: { state: LearnerState; total: number }) {
  const records = Object.values(state.mastery);
  const started = records.filter((m) => m.n_attempts > 0).length;
  const mastered = records.filter((m) => m.n_attempts > 0 && m.p_mastery >= MASTERED).length;
  const items = [
    { label: "Questions answered", value: state.total_attempts },
    { label: "Concepts started", value: `${started}`, sub: `of ${total}` },
    { label: "Concepts mastered", value: `${mastered}`, sub: "95% or higher" },
  ];
  return (
    <div className="grid gap-4 sm:grid-cols-3">
      {items.map((s) => (
        <Card key={s.label} className="p-5">
          <p className="text-sm text-muted">{s.label}</p>
          <p className="mt-2 text-3xl font-semibold tabular-nums tracking-tight text-fg">
            {s.value}
            {s.sub && <span className="ml-1.5 text-sm font-normal text-subtle">{s.sub}</span>}
          </p>
        </Card>
      ))}
    </div>
  );
}

type Row = { id: number; when: string; text: string; detail?: string; up?: boolean; count?: number };

function Activity({ history, names }: { history: StateUpdateView[]; names: Record<string, string> }) {
  const rows = history
    .map((h) => {
      const when = new Date(h.created_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
      if (h.source === "questionnaire") return { id: h.id, when, text: "Set your starting profile from the questionnaire" };
      if (h.source === "attempt") {
        const [cid, [before, after]] = Object.entries(h.delta.mastery_changes)[0] ?? ["", [0, 0]];
        if (!cid) return null;
        const up = after >= before;
        return {
          id: h.id,
          when,
          text: `Answered a question on ${names[cid] ?? cid}`,
          detail: `${Math.round(before * 100)}% → ${Math.round(after * 100)}%`,
          up,
        };
      }
      const traits = Object.keys(h.delta.trait_changes).length;
      return { id: h.id, when, text: traits ? "Your feedback tuned how explanations are written" : "Recorded your feedback on an explanation" };
    })
    .filter(Boolean) as Row[];
  // runs of the same plain event (e.g. several ratings in a row) read better as one line
  const merged: Row[] = [];
  for (const r of rows) {
    const last = merged[merged.length - 1];
    if (last && !r.detail && !last.detail && last.text === r.text) last.count = (last.count ?? 1) + 1;
    else merged.push({ ...r });
  }
  const shown = merged.slice(0, 8);

  return (
    <section className="space-y-4">
      <SectionTitle title="Recent activity" hint="Every change to your estimates, newest first." />
      <Card className="divide-y divide-line">
        {shown.length === 0 && <p className="p-5 text-sm text-muted">Nothing yet. Your first answers will show up here.</p>}
        {shown.map((r) => (
          <div key={r.id} className="flex items-center justify-between gap-4 px-5 py-3.5">
            <div className="min-w-0">
              <p className="truncate text-sm text-fg">
                {r.text}
                {r.count && r.count > 1 && <span className="ml-1.5 text-subtle">× {r.count}</span>}
              </p>
              <p className="text-xs text-subtle">{r.when}</p>
            </div>
            {r.detail && (
              <span className={`flex-none text-sm font-medium tabular-nums ${r.up ? "text-success" : "text-warning"}`}>{r.detail}</span>
            )}
          </div>
        ))}
      </Card>
    </section>
  );
}
