"use client";

import { motion } from "motion/react";
import React, { useMemo, useState } from "react";
import { cn } from "../ui/cn";
import { ease } from "../ui/motion";

export interface AttributionRow {
  name: string;
  label: string;
  value: number; // signed contribution
  display?: string; // the feature's own value, e.g. "42%"
}

/** "+4.1 pts" for probabilities (percentage points), "+0.42" for log-odds. */
export function formatContribution(v: number, unit: "probability" | "logit"): string {
  const sign = v > 0 ? "+" : v < 0 ? "−" : "";
  const abs = Math.abs(v);
  return unit === "probability" ? `${sign}${(abs * 100).toFixed(1)} pts` : `${sign}${abs.toFixed(2)}`;
}

/**
 * Diverging bar chart of feature contributions: right (blue, ▲) raises the predicted chance, left
 * (orange, ▼) lowers it. Every bar is also labelled with its signed value, has a hover/focus
 * tooltip, and the whole chart can be shown as a table, so nothing depends on colour alone.
 * `personal` shows each factor's value for you under its name; `animated` lets the bars glide to
 * new values (e.g. when switching method) instead of regrowing.
 */
export function AttributionChart({
  rows,
  unit,
  limit = 8,
  caption,
  personal = false,
  animated = false,
}: {
  rows: AttributionRow[];
  unit: "probability" | "logit";
  limit?: number;
  caption: string;
  personal?: boolean;
  animated?: boolean;
}) {
  const [all, setAll] = useState(false);
  const [table, setTable] = useState(false);
  const [active, setActive] = useState<string | null>(null);
  const sorted = useMemo(() => [...rows].sort((a, b) => Math.abs(b.value) - Math.abs(a.value)), [rows]);
  const shown = all ? sorted : sorted.slice(0, limit);
  const max = Math.max(...sorted.map((r) => Math.abs(r.value)), 1e-9);

  return (
    <figure className="space-y-3" data-testid="attribution-chart">
      <figcaption className="flex flex-wrap items-center justify-between gap-2 text-xs text-subtle">
        <span>{caption}</span>
        <span className="flex items-center gap-3">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-3 rounded-sm bg-viz-lower" aria-hidden />
            <span aria-hidden className="text-[9px] text-viz-lower">▼</span> lowers
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-3 rounded-sm bg-viz-raise" aria-hidden />
            <span aria-hidden className="text-[9px] text-viz-raise">▲</span> raises
          </span>
          <button type="button" onClick={() => setTable((t) => !t)} className="font-medium text-primary hover:text-primary-hover">
            {table ? "Show chart" : "Show as table"}
          </button>
        </span>
      </figcaption>

      {table ? (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line text-left text-xs text-subtle">
              <th className="py-1.5 font-medium">Factor</th>
              <th className="py-1.5 font-medium">Your value</th>
              <th className="py-1.5 text-right font-medium">Contribution</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((r) => (
              <tr key={r.name} className="border-b border-line/60">
                <td className="py-1.5 pr-3 text-fg">{r.label}</td>
                <td className="py-1.5 pr-3 tabular-nums text-muted">{r.display ?? "—"}</td>
                <td className="py-1.5 text-right tabular-nums text-fg">{formatContribution(r.value, unit)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <ul className="space-y-0.5" onMouseLeave={() => setActive(null)}>
          {shown.map((r, i) => {
            const width = (Math.abs(r.value) / max) * 100;
            const positive = r.value >= 0;
            const text = formatContribution(r.value, unit);
            const grow = { duration: animated ? 0.3 : 0.5, ease, delay: animated ? 0 : i * 0.03 };
            return (
              <motion.li
                key={r.name}
                layout={animated ? "position" : false}
                transition={{ layout: { duration: 0.3, ease } }}
                tabIndex={0}
                onMouseEnter={() => setActive(r.name)}
                onFocus={() => setActive(r.name)}
                onBlur={() => setActive(null)}
                aria-label={`${r.label}${r.display ? ` (${r.display})` : ""}: ${text}`}
                className={cn(
                  // phones: the factor's name on its own line above its bar; wider: one row each
                  "relative grid grid-cols-[minmax(0,1fr)_4rem] items-center gap-x-2 rounded-md px-1.5 py-1 outline-none transition-colors sm:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)_4.5rem] sm:gap-x-3",
                  active === r.name && "bg-surface-2"
                )}
              >
                {/* long names wrap to two lines rather than being cut off; the full name is in the tooltip */}
                <span className="col-span-2 sm:col-span-1" title={r.label}>
                  <span className="block text-[13px] leading-snug text-fg sm:line-clamp-2">{r.label}</span>
                  {personal && r.display && <span className="block text-[11px] tabular-nums text-subtle">you: {r.display}</span>}
                </span>
                <span className="relative flex h-5 items-center">
                  <span className="absolute left-1/2 top-0 h-full w-px bg-viz-neutral" aria-hidden />
                  <span className="relative h-full w-1/2">
                    {!positive && (
                      <motion.span
                        className="absolute right-0 top-1/2 h-2.5 -translate-y-1/2 rounded-l-[4px] bg-viz-lower"
                        initial={{ width: 0 }}
                        animate={{ width: `${width}%` }}
                        transition={grow}
                      />
                    )}
                  </span>
                  <span className="relative h-full w-1/2">
                    {positive && (
                      <motion.span
                        className="absolute left-0 top-1/2 h-2.5 -translate-y-1/2 rounded-r-[4px] bg-viz-raise"
                        initial={{ width: 0 }}
                        animate={{ width: `${width}%` }}
                        transition={grow}
                      />
                    )}
                  </span>
                </span>
                <span className="text-right text-[12px] tabular-nums text-muted">{text}</span>
                {active === r.name && (
                  <span
                    role="tooltip"
                    className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-1 -translate-x-1/2 whitespace-nowrap rounded-lg border border-line bg-surface px-2.5 py-1.5 text-xs text-fg shadow-pop"
                  >
                    <span className="font-medium">{r.label}</span>
                    {r.display && <span className="text-muted"> · your value {r.display}</span>}
                    <span className="block text-muted">
                      {positive ? "Raises" : "Lowers"} the prediction by {text.replace(/^[+−]/, "")}
                    </span>
                  </span>
                )}
              </motion.li>
            );
          })}
        </ul>
      )}
      {!table && sorted.length > limit && (
        <button type="button" onClick={() => setAll((a) => !a)} className="text-xs font-medium text-primary hover:text-primary-hover">
          {all ? "Show the top factors only" : `Show all ${sorted.length} factors`}
        </button>
      )}
    </figure>
  );
}
