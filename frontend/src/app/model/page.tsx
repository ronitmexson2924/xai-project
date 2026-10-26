"use client";

import { motion } from "motion/react";
import React, { useEffect, useState } from "react";
import { AppShell, PageLoading } from "@/components/AppShell";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { ease, fadeUp, Stagger } from "@/components/ui/motion";
import { api, ApiException, ModelCard, ModelMetrics } from "@/lib/api";
import { useLearnerGuard } from "@/lib/guards";

const METRICS: { key: keyof ModelMetrics; label: string; better: "high" | "low"; about: string }[] = [
  { key: "auc", label: "AUC", better: "high", about: "How well it ranks right above wrong answers (0.5 = chance)" },
  { key: "log_loss", label: "Log loss", better: "low", about: "Penalises confident wrong predictions" },
  { key: "brier", label: "Brier", better: "low", about: "Mean squared error of the probabilities" },
  { key: "accuracy", label: "Accuracy", better: "high", about: "Share right when cut at 50%" },
  { key: "ece", label: "ECE", better: "low", about: "Calibration: do 70% predictions come true 70% of the time?" },
];

const METHODS = [
  {
    name: "SHAP",
    paper: "Lundberg & Lee, 2017",
    what: "Shapley values from game theory: each factor's fair share of the gap between your prediction and the average one. The shares add up exactly to the prediction.",
  },
  {
    name: "LIME",
    paper: "Ribeiro et al., 2016",
    what: "Fits a simple straight-line model to the network's answers for slightly changed copies of you. Its R² shows when that simple story is not good enough.",
  },
  {
    name: "LRP",
    paper: "Bach et al., 2015",
    what: "Layer-wise relevance propagation: passes the network's output back through each layer onto the inputs, using the trained weights themselves.",
  },
  {
    name: "DiCE",
    paper: "Mothilal et al., 2020",
    what: "Diverse counterfactuals: a few small, realistic changes to things you can change by practising that would flip the prediction.",
  },
];

export default function ModelPage() {
  const ready = useLearnerGuard({ need: "onboarding" });
  const [card, setCard] = useState<ModelCard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ready) return;
    api.xai
      .modelCard()
      .then(setCard)
      .catch((err) => setError(err instanceof ApiException ? err.message : "Could not load the model card."));
  }, [ready]);

  if (!ready) return <PageLoading />;
  return (
    <AppShell>
      <Stagger className="mx-auto max-w-4xl space-y-8">
        <motion.div variants={fadeUp}>
          <Badge tone="primary">Explainable AI</Badge>
          <h1 className="mt-3 text-2xl font-semibold tracking-tight text-fg sm:text-3xl">How the AI model works</h1>
          <p className="mt-2 max-w-2xl text-muted">
            A neural network trained in Python predicts whether you will answer a question correctly. After each answer
            you can see what it predicted and why, explained four ways. No external AI service is involved: the model
            and every explanation run on this app&apos;s own server.
          </p>
        </motion.div>

        {error && (
          <p role="alert" className="rounded-xl border border-danger/30 bg-danger-soft p-4 text-sm text-danger">
            {error}
          </p>
        )}
        {!card && !error && <CardSkeleton />}
        {card && <CardBody card={card} />}

        <motion.section variants={fadeUp} className="space-y-4">
          <h2 className="text-base font-semibold text-fg">The four explanation methods</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            {METHODS.map((m) => (
              <Card key={m.name} className="p-5">
                <p className="font-semibold text-fg">{m.name}</p>
                <p className="text-xs text-subtle">{m.paper}</p>
                <p className="mt-2 text-sm leading-relaxed text-muted">{m.what}</p>
              </Card>
            ))}
          </div>
        </motion.section>
      </Stagger>
    </AppShell>
  );
}

function CardBody({ card }: { card: ModelCard }) {
  const models = Object.entries(card.test_metrics);
  const best = Object.fromEntries(
    METRICS.map((m) => {
      const values = models.map(([, r]) => r[m.key]);
      return [m.key, m.better === "high" ? Math.max(...values) : Math.min(...values)];
    })
  );
  const labels = Object.fromEntries(card.features.map((f) => [f.name, f.label]));
  const importance = Object.entries(card.global_importance.shap).sort((a, b) => b[1] - a[1]);
  const maxImp = Math.max(...importance.map(([, v]) => v), 1e-9);
  const q = card.explanation_quality;
  const nn = card.test_metrics["neural network (this model)"];
  const bktAuc = card.test_metrics["BKT (the learner model)"]?.auc;

  return (
    <>
      <motion.div variants={fadeUp} className="grid gap-4 sm:grid-cols-3">
        <Stat label="What it predicts" value="P(correct)" sub="for the next question, before you answer" />
        <Stat
          label="Network (chosen on validation data)"
          value={[card.features.length, ...card.model_selection.chosen.hidden, 1].join(" → ")}
          sub={`multilayer perceptron, ReLU, sigmoid; best of ${card.model_selection.candidates.length} candidates`}
        />
        <Stat
          label="Test AUC"
          value={nn ? nn.auc.toFixed(2) : "—"}
          sub={bktAuc !== undefined ? `BKT on the same answers: ${bktAuc.toFixed(2)}` : undefined}
        />
      </motion.div>

      <motion.div variants={fadeUp}>
        <Card className="space-y-4 p-6">
          <div>
            <h2 className="font-semibold text-fg">How well it predicts</h2>
            <p className="mt-0.5 text-sm text-muted">
              On {card.rows.test.toLocaleString()} answers from {card.learners.test} learners it never saw during
              training ({card.trained_on}). The best value in each column is marked.
            </p>
          </div>
          <div className="relative overflow-x-auto" tabIndex={0} role="region" aria-label="Test metrics by model">
            <table className="w-full min-w-[520px] text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs text-subtle">
                  <th className="py-2 pr-3 font-medium">Model</th>
                  {METRICS.map((m) => (
                    <th key={m.key} className="py-2 pr-3 text-right font-medium" title={m.about}>
                      {m.label} {m.better === "high" ? "↑" : "↓"}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {models.map(([name, r]) => (
                  <tr key={name} className="border-b border-line/60">
                    <td className="py-2 pr-3 text-fg">{name}</td>
                    {METRICS.map((m) => {
                      const isBest = Math.abs(r[m.key] - best[m.key]) < 1e-9;
                      return (
                        <td key={m.key} className={`py-2 pr-3 text-right tabular-nums ${isBest ? "font-semibold text-fg" : "text-muted"}`}>
                          {r[m.key].toFixed(3)}
                          {isBest && <span className="sr-only"> (best)</span>}
                          {isBest && <span aria-hidden> •</span>}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </motion.div>

      <motion.div variants={fadeUp}>
        <Card className="space-y-4 p-6" data-testid="global-importance">
          <div>
            <h2 className="font-semibold text-fg">What drives its predictions overall</h2>
            <p className="mt-0.5 text-sm text-muted">
              Average size of each factor&apos;s SHAP contribution over {q.rows_explained} test answers, in percentage
              points.
            </p>
          </div>
          <ul className="space-y-1.5">
            {importance.map(([name, v], i) => (
              <li key={name} className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)_3.5rem] items-center gap-3 text-[13px]">
                <span className="leading-snug text-fg sm:line-clamp-2" title={labels[name] ?? name}>
                  {labels[name] ?? name}
                </span>
                <span className="h-2.5 rounded-r-[4px] bg-surface-2">
                  <motion.span
                    className="block h-full rounded-r-[4px] bg-viz-raise"
                    initial={{ width: 0 }}
                    animate={{ width: `${(v / maxImp) * 100}%` }}
                    transition={{ duration: 0.6, ease, delay: i * 0.03 }}
                  />
                </span>
                <span className="text-right tabular-nums text-muted">{(v * 100).toFixed(1)}</span>
              </li>
            ))}
          </ul>
        </Card>
      </motion.div>

      <motion.div variants={fadeUp}>
        <Card className="space-y-3 p-6">
          <h2 className="font-semibold text-fg">Can the explanations be trusted?</h2>
          <ul className="grid gap-3 text-sm sm:grid-cols-2">
            <Check
              title="The methods agree"
              detail={Object.entries(q.method_agreement_spearman)
                .map(([k, v]) => `${k.replace("~", " & ").toUpperCase()} ρ ${v.toFixed(2)}`)
                .join(" · ")}
            />
            <Check title="LIME's simple model fits" detail={`median R² ${q.lime_median_r2.toFixed(2)}`} />
            <Check
              title="Counterfactuals really flip the prediction"
              detail={`${Math.round(q.counterfactual_valid * 100)}% valid, about ${q.counterfactual_mean_features_changed.toFixed(1)} factors changed, found for ${Math.round(q.counterfactual_found * 100)}% of answers`}
            />
            <Check
              title="SHAP points at what matters (deletion test)"
              detail={`removing its top 3 factors moves the prediction ${(q.deletion_top3_shap * 100).toFixed(1)} pts; 3 random factors ${(q.deletion_random3 * 100).toFixed(1)} pts`}
            />
          </ul>
        </Card>
      </motion.div>

      <motion.div variants={fadeUp}>
        <Card className="space-y-2 p-6">
          <h2 className="font-semibold text-fg">Limitations</h2>
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
            {card.limitations.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </Card>
      </motion.div>
    </>
  );
}

/** The card's shape while it loads: three stats, the metrics table, the importance bars. */
function CardSkeleton() {
  const bar = "animate-pulse rounded bg-surface-2";
  return (
    <div className="space-y-8" aria-busy role="status" aria-label="Loading the model card" data-testid="model-skeleton">
      <div className="grid gap-4 sm:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <Card key={i} className="space-y-3 p-5">
            <div className={`h-3 w-24 ${bar}`} />
            <div className={`h-7 w-32 ${bar}`} />
            <div className={`h-2.5 w-40 ${bar}`} />
          </Card>
        ))}
      </div>
      <Card className="space-y-4 p-6">
        <div className={`h-4 w-40 ${bar}`} />
        <div className={`h-3 w-3/4 ${bar}`} />
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className={`h-3 ${bar}`} />
        ))}
      </Card>
      <Card className="space-y-3 p-6">
        <div className={`h-4 w-52 ${bar}`} />
        {[90, 70, 55, 40, 30, 22].map((w) => (
          <div key={w} className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)_3.5rem] items-center gap-3">
            <div className={`h-3 w-3/4 ${bar}`} />
            <div className={`h-2.5 ${bar}`} style={{ width: `${w}%` }} />
            <div className={`h-3 ${bar}`} />
          </div>
        ))}
      </Card>
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Card className="p-5">
      <p className="text-sm text-muted">{label}</p>
      <p className="mt-1.5 text-2xl font-semibold tabular-nums tracking-tight text-fg">{value}</p>
      {sub && <p className="mt-1 text-xs text-subtle">{sub}</p>}
    </Card>
  );
}

function Check({ title, detail }: { title: string; detail: string }) {
  return (
    <li className="rounded-lg border border-line bg-surface-2/50 p-3">
      <p className="font-medium text-fg">{title}</p>
      <p className="mt-0.5 text-xs text-muted">{detail}</p>
    </li>
  );
}
