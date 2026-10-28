"use client";

import React from "react";
import type { ReportMatrixRow } from "@/lib/api";
import { linear, signed, symmetricDomain, ticks } from "@/lib/report-charts";
import { ChartFrame, DataTable, DirectionLegend, fit } from "./ChartFrame";

const colour = (v: number) => (v >= 0 ? "var(--viz-raise)" : "var(--viz-lower)");

/**
 * LIME: the top 10 factors of a simple straight-line model fitted around this one prediction.
 * Bars right of the centre line raised the predicted chance, bars to the left lowered it.
 */
export function LimeBars({ matrix, r2 }: { matrix: ReportMatrixRow[]; r2: number | null | undefined }) {
  const rows = matrix
    .filter((r) => r.lime !== null && r.lime !== undefined)
    .sort((a, b) => Math.abs(b.lime!) - Math.abs(a.lime!))
    .slice(0, 10);
  if (!rows.length) return null;
  const domain = symmetricDomain(rows.map((r) => r.lime!));
  const row = 26;
  return (
    <ChartFrame
      id="lime-bars"
      testId="lime-bars"
      title="LIME: the top 10 factors for this prediction"
      caption={`LIME fits a simple straight-line model to the network's answers for slightly changed copies of this learner. Each bar is a factor's weight in that simple model, in percentage points.${
        r2 !== null && r2 !== undefined ? ` The simple model fits the network here with R² = ${r2.toFixed(2)} (1 is a perfect fit).` : ""
      }`}
      legend={<DirectionLegend />}
      table={<DataTable head={["Factor", "Value", "LIME weight"]} rows={rows.map((r) => [r.label, r.display, signed(r.lime)])} />}
    >
      {(width) => {
        const labelW = Math.min(230, Math.max(110, width * 0.38));
        const valueW = 70;
        const x = linear(domain, [labelW, width - valueW]);
        const height = rows.length * row + 26;
        return (
          <svg width={width} height={height} role="img" aria-label="LIME factor weights">
            <line x1={x(0)} x2={x(0)} y1={0} y2={rows.length * row} className="stroke-line-strong" />
            {rows.map((r, i) => {
              const v = r.lime!;
              const y = i * row;
              return (
                <g key={r.name}>
                  <title>{`${r.label} (${r.display}): ${signed(v)}`}</title>
                  <text x={labelW - 8} y={y + row / 2 + 4} textAnchor="end" className="fill-fg text-[12px]">
                    {fit(r.label, labelW - 12)}
                  </text>
                  <rect x={Math.min(x(0), x(v))} y={y + 6} width={Math.max(1.5, Math.abs(x(v) - x(0)))} height={row - 12} rx={3} fill={colour(v)} />
                  <text x={width - 4} y={y + row / 2 + 4} textAnchor="end" className="fill-muted text-[11px] tabular-nums">
                    {v >= 0 ? "▲" : "▼"} {signed(v)}
                  </text>
                </g>
              );
            })}
            {ticks(domain[0], domain[1], 4).map((t) => (
              <text key={t} x={x(t)} y={rows.length * row + 16} textAnchor="middle" className="fill-subtle text-[10px] tabular-nums">
                {signed(t).replace(" pts", "")}
              </text>
            ))}
          </svg>
        );
      }}
    </ChartFrame>
  );
}

/**
 * SHAP and LIME side by side for the same factors: when the paired bars point the same way and
 * have similar lengths, the two methods tell the same story about this prediction.
 */
export function ShapVsLime({ matrix }: { matrix: ReportMatrixRow[] }) {
  const rows = matrix.filter((r) => r.shap !== null && r.lime !== null && r.shap !== undefined && r.lime !== undefined).slice(0, 8);
  if (!rows.length) return null;
  const domain = symmetricDomain(rows.flatMap((r) => [r.shap!, r.lime!]));
  const row = 36;
  return (
    <ChartFrame
      id="shap-vs-lime"
      testId="shap-vs-lime"
      title="SHAP and LIME compared"
      caption="For each of the strongest factors, the solid bar is SHAP and the striped bar is LIME. Bars pointing the same way with similar lengths mean the two methods agree about that factor."
      legend={
        <>
          <DirectionLegend />
          <span className="inline-flex items-center gap-1.5">
            <svg width="14" height="10" aria-hidden>
              <rect width="14" height="10" rx="2" fill="var(--text-muted)" />
            </svg>
            SHAP
          </span>
          <span className="inline-flex items-center gap-1.5">
            <svg width="14" height="10" aria-hidden>
              <defs>
                <pattern id="legend-hatch" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                  <rect width="2" height="4" fill="var(--text-muted)" />
                </pattern>
              </defs>
              <rect width="14" height="10" rx="2" fill="url(#legend-hatch)" stroke="var(--text-muted)" />
            </svg>
            LIME
          </span>
        </>
      }
      table={<DataTable head={["Factor", "SHAP", "LIME"]} rows={rows.map((r) => [r.label, signed(r.shap), signed(r.lime)])} />}
    >
      {(width) => {
        const labelW = Math.min(230, Math.max(110, width * 0.38));
        const x = linear(domain, [labelW, width - 12]);
        return (
          <svg width={width} height={rows.length * row + 4} role="img" aria-label="SHAP and LIME contributions side by side">
            <defs>
              {(["raise", "lower"] as const).map((k) => (
                <pattern key={k} id={`hatch-${k}`} width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                  <rect width="5" height="5" fill={`var(--viz-${k})`} opacity="0.25" />
                  <rect width="2.2" height="5" fill={`var(--viz-${k})`} />
                </pattern>
              ))}
            </defs>
            <line x1={x(0)} x2={x(0)} y1={0} y2={rows.length * row} className="stroke-line-strong" />
            {rows.map((r, i) => {
              const y = i * row;
              const bar = (v: number, dy: number, hatched: boolean, name: string) => (
                <rect
                  x={Math.min(x(0), x(v))}
                  y={y + dy}
                  width={Math.max(1.5, Math.abs(x(v) - x(0)))}
                  height={12}
                  rx={2}
                  fill={hatched ? `url(#hatch-${v >= 0 ? "raise" : "lower"})` : colour(v)}
                  stroke={hatched ? colour(v) : undefined}
                  strokeWidth={hatched ? 0.8 : undefined}
                >
                  <title>{`${r.label}, ${name}: ${signed(v)}`}</title>
                </rect>
              );
              return (
                <g key={r.name}>
                  <text x={labelW - 8} y={y + row / 2 + 4} textAnchor="end" className="fill-fg text-[12px]">
                    {fit(r.label, labelW - 12)}
                  </text>
                  {bar(r.shap!, 5, false, "SHAP")}
                  {bar(r.lime!, 19, true, "LIME")}
                </g>
              );
            })}
          </svg>
        );
      }}
    </ChartFrame>
  );
}
