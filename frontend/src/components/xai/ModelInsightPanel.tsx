"use client";

import Link from "next/link";
import { AnimatePresence, motion } from "motion/react";
import React, { useState } from "react";
import { api, ApiException, MethodAttribution, ModelInsight } from "@/lib/api";
import { ENGAGEMENT_UI } from "@/lib/engagement";
import { BASELINE_NOTE, describeChange, pathStep, pct, secondPersonSummary } from "@/lib/moments";
import { Badge } from "../ui/Badge";
import { cn } from "../ui/cn";
import { ease } from "../ui/motion";
import { AttributionChart } from "./AttributionChart";

const AGREEMENT_LABEL: Record<string, string> = {
  "shap~lime": "SHAP and LIME",
  "shap~lrp": "SHAP and LRP",
  "lime~lrp": "LIME and LRP",
};

function unitOf(a: MethodAttribution): "probability" | "logit" {
  return a.unit.startsWith("logit") ? "logit" : "probability";
}

function agreementWord(rho: number): string {
  return rho >= 0.7 ? "agree" : rho >= 0.4 ? "partly agree" : "disagree";
}

/** What a Spearman ρ means, for the agreement chips' tooltips. */
function agreementMeaning(rho: number): string {
  const how =
    rho >= 0.85 ? "almost the same way" : rho >= 0.7 ? "much the same way" : rho >= 0.4 ? "only partly the same way" : "differently";
  return `ρ ${rho.toFixed(2)}: the two methods rank the factors ${how} (1 = identical order, 0 = unrelated).`;
}

/**
 * What the performance model (a trained neural network) predicted for this question before it
 * was answered, and why: SHAP, LIME and LRP attributions, DiCE counterfactuals, and how far the
 * methods agree. Loaded only when opened, unless the page already fetched it (`initial`).
 */
export function ModelInsightPanel({
  recommendationId,
  initial = null,
  answeredCorrectly,
}: {
  recommendationId: string;
  initial?: ModelInsight | null;
  /** the attempt's own result, for an insight fetched before the answer was marked */
  answeredCorrectly?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [fetched, setInsight] = useState<ModelInsight | null>(null);
  const loaded = fetched ?? initial;
  const insight = loaded && answeredCorrectly !== undefined ? { ...loaded, answered_correctly: answeredCorrectly } : loaded;
  const [error, setError] = useState<string | null>(null);
  const [method, setMethod] = useState("shap");

  const toggle = async () => {
    const next = !open;
    setOpen(next);
    if (!next || insight) return;
    try {
      setInsight(await api.xai.model(recommendationId));
    } catch (err) {
      setError(err instanceof ApiException ? err.message : "Could not load the model's explanation.");
    }
  };

  return (
    <div className="rounded-xl border border-line bg-surface shadow-card" data-testid="model-insight">
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-3 px-5 py-4 text-left"
      >
        <span className="flex items-center gap-3">
          <span className="flex h-8 w-8 flex-none items-center justify-center rounded-lg bg-primary-soft text-primary" aria-hidden>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <circle cx="5" cy="6" r="2" />
              <circle cx="5" cy="18" r="2" />
              <circle cx="12" cy="12" r="2" />
              <circle cx="19" cy="7" r="2" />
              <circle cx="19" cy="17" r="2" />
              <path d="M7 6.5 10 11M7 17.5l3-4.5M14 11.5l3-3.5M14 12.5l3 3.5" />
            </svg>
          </span>
          <span>
            {ENGAGEMENT_UI ? (
              <>
                <span className="block text-sm font-medium text-fg">How the model saw you before this question</span>
                <span className="block text-xs text-muted">Its prediction for you, explained with SHAP, LIME, LRP and DiCE</span>
              </>
            ) : (
              <>
                <span className="block text-sm font-medium text-fg">What the AI model predicted</span>
                <span className="block text-xs text-muted">A neural network&apos;s guess, explained with SHAP, LIME, LRP and DiCE</span>
              </>
            )}
          </span>
        </span>
        <motion.span animate={{ rotate: open ? 180 : 0 }} className="text-subtle" aria-hidden>
          ▾
        </motion.span>
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: ENGAGEMENT_UI ? 0.2 : 0.3, ease }}
            className="overflow-hidden"
          >
            <div className="space-y-6 border-t border-line px-5 py-5">
              {!insight && !error && (
                <div className="space-y-3" aria-busy>
                  <div className="h-10 w-32 animate-pulse rounded bg-surface-2" />
                  <div className="h-3 w-3/4 animate-pulse rounded bg-surface-2" />
                  <div className="h-32 animate-pulse rounded bg-surface-2" />
                </div>
              )}
              {error && <p className="text-sm text-danger">{error}</p>}
              {insight && <InsightBody insight={insight} method={method} setMethod={setMethod} />}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function InsightBody({
  insight,
  method,
  setMethod,
}: {
  insight: ModelInsight;
  method: string;
  setMethod: (m: string) => void;
}) {
  const display = Object.fromEntries(insight.features.map((f) => [f.name, f.display]));
  const labels = Object.fromEntries(insight.features.map((f) => [f.name, f.label]));
  const current = insight.attributions.find((a) => a.method === method) ?? insight.attributions[0];
  const rows = Object.entries(current.contributions).map(([name, value]) => ({
    name,
    label: labels[name] ?? name,
    value,
    display: display[name],
  }));
  const outcome = insight.answered_correctly;

  return (
    <>
      <div className="flex flex-wrap items-end gap-x-6 gap-y-2">
        <div>
          <p className="text-xs text-subtle">{ENGAGEMENT_UI ? "Your predicted chance of a correct answer" : "Predicted chance of a correct answer"}</p>
          <p className="text-[40px] font-semibold leading-tight tabular-nums tracking-tight text-fg" data-testid="model-prediction">
            {pct(insight.p_correct)}%
          </p>
        </div>
        {outcome !== null && (
          <Badge tone={outcome ? "success" : "neutral"}>
            <span aria-hidden>{outcome ? "✓" : "✕"}</span>
            {outcome ? "You answered correctly" : "You answered incorrectly"}
          </Badge>
        )}
      </div>
      <p className="text-sm leading-relaxed text-muted" data-testid="model-summary">
        {ENGAGEMENT_UI ? secondPersonSummary(insight) : insight.summary}
      </p>

      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="label-caps">Why: what each factor contributed</h3>
          <div role="tablist" aria-label="Explanation method" className="inline-flex rounded-lg border border-line bg-surface-2 p-0.5">
            {insight.attributions.map((a) => (
              <button
                key={a.method}
                type="button"
                role="tab"
                aria-selected={a.method === current.method}
                onClick={() => setMethod(a.method)}
                className={cn(
                  "rounded-md px-3 py-1 text-xs font-medium transition-colors",
                  a.method === current.method ? "bg-surface text-fg shadow-card" : "text-muted hover:text-fg"
                )}
              >
                {a.title}
              </button>
            ))}
          </div>
        </div>
        <p className="text-xs leading-relaxed text-muted">
          {current.about}
          {current.fidelity !== null && current.fidelity !== undefined && (
            <>
              {" "}
              <Badge tone={current.fidelity >= 0.7 ? "success" : current.fidelity >= 0.4 ? "warning" : "neutral"}>
                R² {current.fidelity.toFixed(2)}
              </Badge>
            </>
          )}
        </p>
        {ENGAGEMENT_UI && BASELINE_NOTE[current.method] && (
          <p className="text-xs leading-relaxed text-subtle" data-testid="baseline-note">
            {BASELINE_NOTE[current.method]}
          </p>
        )}
        <AttributionChart
          key={ENGAGEMENT_UI ? undefined : current.method}
          rows={rows}
          unit={unitOf(current)}
          personal={ENGAGEMENT_UI}
          animated={ENGAGEMENT_UI}
          caption={
            unitOf(current) === "probability"
              ? `Percentage points, starting from ${pct(current.base)}% ${
                  ENGAGEMENT_UI && current.method === "lime" ? "(LIME's own starting point)" : "for an average learner"
                }`
              : "Relevance in log-odds (positive raises the chance)"
          }
        />
        <ul className="flex flex-wrap gap-2" aria-label="How far the methods agree">
          {Object.entries(insight.agreement).map(([pair, rho]) => (
            <li key={pair} title={ENGAGEMENT_UI ? agreementMeaning(rho) : undefined}>
              <Badge tone={rho >= 0.7 ? "success" : rho >= 0.4 ? "warning" : "neutral"}>
                {AGREEMENT_LABEL[pair] ?? pair} {agreementWord(rho)} (ρ {rho.toFixed(2)})
                {ENGAGEMENT_UI && <span className="sr-only">. {agreementMeaning(rho)}</span>}
              </Badge>
            </li>
          ))}
        </ul>
      </section>

      <section className="space-y-2" data-testid="counterfactuals">
        <h3 className="label-caps">
          {ENGAGEMENT_UI
            ? insight.p_correct < 0.5
              ? "Your path to a higher prediction (DiCE)"
              : "What would change the model’s mind (DiCE)"
            : insight.p_correct < 0.5
              ? "What would make the model expect a correct answer (DiCE)"
              : "What would make the model expect a wrong answer instead (DiCE)"}
        </h3>
        {insight.counterfactuals.length === 0 ? (
          <p className="text-sm text-muted">No small, realistic change would flip this prediction.</p>
        ) : ENGAGEMENT_UI && insight.p_correct < 0.5 ? (
          <ul className="space-y-2">
            {insight.counterfactuals.map((cf, i) => (
              <li key={i} className="rounded-lg border border-line bg-surface-2/50 px-4 py-3 text-sm">
                <ul className="space-y-1.5">
                  {cf.changes.map((c) => {
                    const step = pathStep(c);
                    return (
                      <li key={c.name} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
                        <span className="text-fg">{step.action}</span>
                        <span className="inline-flex items-center gap-1.5 text-xs tabular-nums text-muted">
                          <span className="rounded border border-line bg-surface px-1.5 py-0.5">now {step.now}</span>
                          <span aria-hidden>→</span>
                          <span className="sr-only">to</span>
                          <span className="rounded border border-primary/30 bg-primary-soft px-1.5 py-0.5 font-medium text-primary">{step.target}</span>
                        </span>
                      </li>
                    );
                  })}
                </ul>
                <p className="mt-2 text-xs text-muted">
                  Then the model would predict <span className="font-semibold tabular-nums text-fg">{pct(cf.p_correct)}%</span> for you.
                </p>
              </li>
            ))}
          </ul>
        ) : (
          <ul className="space-y-2">
            {insight.counterfactuals.map((cf, i) => (
              <li key={i} className="rounded-lg border border-line bg-surface-2/50 px-4 py-3 text-sm">
                <p className="text-fg">
                  If{" "}
                  {cf.changes.map((c, j) => (
                    <React.Fragment key={c.name}>
                      {j > 0 && (j === cf.changes.length - 1 ? " and " : ", ")}
                      {describeChange(c)}
                    </React.Fragment>
                  ))}
                  , the model would predict <span className="font-semibold tabular-nums">{pct(cf.p_correct)}%</span>.
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      {insight.notes.length > 0 && (
        <ul className="space-y-1 rounded-lg border border-warning/30 bg-warning-soft p-3 text-sm text-fg">
          {insight.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}

      <details className="group text-sm">
        <summary className="label-caps cursor-pointer">
          The inputs the model saw
        </summary>
        <dl className="mt-3 grid grid-cols-1 gap-x-6 gap-y-1.5 sm:grid-cols-2">
          {insight.features.map((f) => (
            <div key={f.name} className="flex justify-between gap-3 border-b border-line/60 py-1">
              <dt className="text-muted">{f.label}</dt>
              <dd className="tabular-nums text-fg">{f.display}</dd>
            </div>
          ))}
        </dl>
      </details>

      <p className="text-xs text-subtle">
        {insight.model.architecture}. Trained on {insight.model.trained_on}. On learners it never saw: AUC{" "}
        {insight.model.test_auc.toFixed(2)} (BKT {insight.model.bkt_auc.toFixed(2)}). It predicts, it does not choose your
        questions.{" "}
        <Link href="/model" className="font-medium text-primary hover:text-primary-hover">
          How the model works →
        </Link>
      </p>
    </>
  );
}
