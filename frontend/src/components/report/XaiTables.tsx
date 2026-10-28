"use client";

import React, { useState } from "react";
import type { ReportMatrixRow, UserReport } from "@/lib/api";
import { signed } from "@/lib/report-charts";
import { cn } from "../ui/cn";

const METHOD_NAME: Record<string, string> = { shap: "SHAP", lime: "LIME", lrp: "LRP" };

/** A signed number for a matrix cell; the unit is in the column header. */
const num = (v: number | null | undefined, unit: "pts" | "logit" = "pts") => signed(v, unit).replace(" pts", "");

function Direction({ row }: { row: ReportMatrixRow }) {
  if (row.direction === "neutral") return <span className="text-subtle">no push</span>;
  const up = row.direction === "raises";
  // the glyph carries the chart colour (a graphic); the word stays in text colour for contrast
  return (
    <span className="inline-flex items-center gap-1 font-medium text-fg">
      <span aria-hidden className={up ? "text-viz-raise" : "text-viz-lower"}>
        {up ? "▲" : "▼"}
      </span>
      {up ? "raises" : "lowers"}
    </span>
  );
}

/**
 * The XAI matrix: one row per factor, strongest first, with what each method says about it for
 * this prediction, the direction, whether the methods agree on it, and what it means in plain words.
 */
export function XaiMatrix({ matrix }: { matrix: ReportMatrixRow[] }) {
  const [all, setAll] = useState(false);
  const rows = all ? matrix : matrix.slice(0, 8);
  return (
    <div className="space-y-2" data-testid="xai-matrix">
      <div className="relative overflow-x-auto rounded-xl border border-line bg-surface shadow-card" tabIndex={0} role="region" aria-label="XAI matrix">
        <table className="w-full min-w-[760px] text-sm">
          <thead>
            <tr className="border-b border-line bg-surface-2/60 text-left text-xs text-subtle">
              <th className="px-4 py-2 font-medium">Factor</th>
              <th className="px-3 py-2 text-right font-medium">Value</th>
              <th className="px-3 py-2 text-right font-medium" title="Change in the predicted chance, in percentage points">
                SHAP <span className="font-normal">(pts)</span>
              </th>
              <th className="px-3 py-2 text-right font-medium" title="Weight in LIME's local straight-line model, in percentage points">
                LIME <span className="font-normal">(pts)</span>
              </th>
              <th className="px-3 py-2 text-right font-medium" title="Relevance from the network's weights, in log-odds">
                LRP <span className="font-normal">(log-odds)</span>
              </th>
              <th className="px-3 py-2 font-medium">Direction</th>
              <th className="px-3 py-2 font-medium">Methods agree</th>
              <th className="px-3 py-2 text-right font-medium" title="Average SHAP over the recent predictions">
                Typical <span className="font-normal">(pts)</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.name} className="border-b border-line/60 align-top last:border-0">
                <td className="px-4 py-2.5">
                  <span className="block font-medium text-fg">{r.label}</span>
                  <span className="block text-xs text-muted">{r.meaning}</span>
                </td>
                <td className="whitespace-nowrap px-3 py-2.5 text-right tabular-nums text-fg">{r.display}</td>
                <td className="whitespace-nowrap px-3 py-2.5 text-right tabular-nums text-fg">{num(r.shap)}</td>
                <td className="whitespace-nowrap px-3 py-2.5 text-right tabular-nums text-fg">{num(r.lime)}</td>
                <td className="whitespace-nowrap px-3 py-2.5 text-right tabular-nums text-fg">{num(r.lrp, "logit")}</td>
                <td className="px-3 py-2.5 text-xs">
                  <Direction row={r} />
                </td>
                <td className="px-3 py-2.5 text-xs">
                  {r.consistent === null || r.consistent === undefined ? (
                    <span className="text-subtle">—</span>
                  ) : r.consistent ? (
                    <span className="whitespace-nowrap text-success">✓ same direction</span>
                  ) : (
                    <span className="whitespace-nowrap text-muted">≠ they differ</span>
                  )}
                </td>
                <td className="whitespace-nowrap px-3 py-2.5 text-right tabular-nums text-muted">{num(r.recent_shap)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {matrix.length > 8 && (
        <button type="button" onClick={() => setAll((a) => !a)} className="no-print text-xs font-medium text-primary hover:text-primary-hover">
          {all ? "Show the top 8 factors" : `Show all ${matrix.length} factors`}
        </button>
      )}
    </div>
  );
}

function Metric({ label, value, about, tone = "neutral" }: { label: string; value: string; about: string; tone?: "good" | "neutral" | "warn" }) {
  return (
    <div className="rounded-lg border border-line bg-surface p-3">
      <p className="text-xs text-muted">{label}</p>
      <p className={cn("mt-0.5 text-lg font-semibold tabular-nums", tone === "good" ? "text-success" : tone === "warn" ? "text-warning" : "text-fg")}>{value}</p>
      <p className="mt-0.5 text-xs leading-relaxed text-subtle">{about}</p>
    </div>
  );
}

/** How far the methods agree, and how good each explanation is. */
export function AgreementAndQuality({ agreement, quality }: { agreement: UserReport["agreement"]; quality: UserReport["quality"] }) {
  const pairName = (pair: string) =>
    pair
      .split("~")
      .map((m) => METHOD_NAME[m] ?? m)
      .join(" and ");
  const dice = quality.dice;
  return (
    <div className="grid gap-4 lg:grid-cols-2" data-testid="xai-quality">
      <section className="space-y-3 rounded-xl border border-line bg-surface p-4 shadow-card sm:p-5">
        <h3 className="text-sm font-semibold text-fg">Do the methods agree?</h3>
        <p className="text-xs text-muted">
          Rank correlation of the factors (1 = identical order, 0 = unrelated) and how many of their top 5 factors are shared.
        </p>
        {agreement.length === 0 ? (
          <p className="text-sm text-muted">Fewer than two methods ran, so there is nothing to compare.</p>
        ) : (
          <ul className="space-y-2">
            {agreement.map((a) => (
              <li key={a.pair} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-line px-3 py-2 text-sm">
                <span className="text-fg">{pairName(a.pair)}</span>
                <span className="flex items-center gap-3 text-xs tabular-nums text-muted">
                  <span>ρ {a.spearman.toFixed(2)}</span>
                  <span>top-5 overlap {Math.round(a.top_k_overlap * 100)}%</span>
                  <span className={cn("rounded-full px-2 py-0.5 font-medium", a.spearman >= 0.7 ? "bg-success-soft text-success" : a.spearman >= 0.4 ? "bg-warning-soft text-warning" : "bg-surface-2 text-muted")}>
                    {a.verdict}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
      <section className="space-y-3 rounded-xl border border-line bg-surface p-4 shadow-card sm:p-5">
        <h3 className="text-sm font-semibold text-fg">How good are the explanations?</h3>
        <div className="grid gap-2 sm:grid-cols-2">
          {quality.lime_r2 !== null && quality.lime_r2 !== undefined && (
            <Metric
              label="LIME local fit (R²)"
              value={quality.lime_r2.toFixed(2)}
              tone={quality.lime_r2 >= 0.7 ? "good" : quality.lime_r2 >= 0.4 ? "neutral" : "warn"}
              about="How well LIME's straight line matches the network near this learner. Above 0.7 is a good fit."
            />
          )}
          {quality.shap_additivity_error !== null && quality.shap_additivity_error !== undefined && (
            <Metric
              label="SHAP completeness error"
              value={quality.shap_additivity_error < 1e-4 ? "< 0.0001" : quality.shap_additivity_error.toFixed(4)}
              tone={quality.shap_additivity_error < 1e-4 ? "good" : "warn"}
              about="Average prediction plus all SHAP values, minus this prediction. 0 means nothing is left unexplained."
            />
          )}
          {quality.lrp_conservation_error !== null && quality.lrp_conservation_error !== undefined && (
            <Metric
              label="LRP relevance not on inputs"
              value={quality.lrp_conservation_error.toFixed(3)}
              about="Log-odds absorbed by the network's biases rather than assigned to a factor. Small is good."
            />
          )}
          {dice && (
            <>
              <Metric
                label="DiCE validity"
                value={`${Math.round(dice.validity * 100)}%`}
                tone={dice.validity >= 0.75 ? "good" : "neutral"}
                about={`${dice.found} of ${dice.requested} requested counterfactuals really move the prediction across 50%.`}
              />
              {dice.proximity !== null && dice.proximity !== undefined && (
                <Metric
                  label="DiCE proximity"
                  value={dice.proximity.toFixed(2)}
                  about="Average distance from this learner, in typical-variation units. Smaller means more realistic, smaller changes."
                />
              )}
              {dice.sparsity !== null && dice.sparsity !== undefined && (
                <Metric label="DiCE sparsity" value={dice.sparsity.toFixed(1)} about="Average number of factors each counterfactual changes. Fewer is easier to act on." />
              )}
              {dice.diversity !== null && dice.diversity !== undefined && (
                <Metric label="DiCE diversity" value={dice.diversity.toFixed(2)} about="Average distance between the counterfactuals. Larger means more different options." />
              )}
            </>
          )}
        </div>
      </section>
    </div>
  );
}

/** DiCE counterfactuals: the learner now, and each option with the changed values highlighted. */
export function CounterfactualTable({ table }: { table: NonNullable<UserReport["counterfactuals"]> }) {
  const pct = (p: number) => `${Math.round(p * 100)}%`;
  const changedRows = table.features.map((_, i) => table.options.some((o) => o.changed[i]));
  return (
    <figure className="min-w-0 space-y-3 rounded-xl border border-line bg-surface p-4 shadow-card break-inside-avoid sm:p-5" data-testid="dice-table" aria-labelledby="dice-title">
      <h3 id="dice-title" className="text-sm font-semibold text-fg">
        DiCE: what would change the prediction
      </h3>
      {table.options.length === 0 ? (
        <p className="text-sm text-muted">No small, realistic change would move this prediction across 50%.</p>
      ) : (
        <div className="relative overflow-x-auto" tabIndex={0} role="region" aria-label="Counterfactual table">
          <table className="w-full min-w-[520px] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs text-subtle">
                <th className="py-2 pr-3 font-medium">Factor</th>
                <th className="py-2 pr-3 text-right font-medium">Now</th>
                {table.options.map((_, k) => (
                  <th key={k} className="py-2 pr-3 text-right font-medium">
                    Option {k + 1}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.features.map((name, i) =>
                // factors no option changes are left out, so the changes stand out
                changedRows[i] ? (
                  <tr key={name} className="border-b border-line/60">
                    <td className="py-2 pr-3 text-fg">{table.labels[i]}</td>
                    <td className="py-2 pr-3 text-right tabular-nums text-muted">{table.now[i]}</td>
                    {table.options.map((o, k) => (
                      <td key={k} className="py-1 pr-1 text-right tabular-nums">
                        {o.changed[i] ? (
                          <span className="inline-block rounded-md bg-primary-soft px-2 py-1 font-semibold text-primary ring-1 ring-primary/30">
                            {o.values[i]}
                            <span className="sr-only"> (changed)</span>
                          </span>
                        ) : (
                          <span className="px-2 text-subtle">{o.values[i]}</span>
                        )}
                      </td>
                    ))}
                  </tr>
                ) : null
              )}
              <tr>
                <td className="pt-2.5 pr-3 font-medium text-fg">Predicted chance</td>
                <td className="pt-2.5 pr-3 text-right font-semibold tabular-nums text-fg">{pct(table.p_now)}</td>
                {table.options.map((o, k) => (
                  <td key={k} className="pt-2.5 pr-3 text-right font-semibold tabular-nums text-fg">
                    {pct(o.p_correct)}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      )}
      <figcaption className="text-xs leading-relaxed text-muted">
        Each option is a small, realistic change that would move the prediction {table.direction === "higher" ? "above" : "below"} 50%. Only things a
        learner can change are varied: questionnaire answers and the question&apos;s difficulty stay fixed, answered questions can&apos;t be un-answered, and a
        misconception can only be cleared. Highlighted values are the ones that change.
      </figcaption>
    </figure>
  );
}
