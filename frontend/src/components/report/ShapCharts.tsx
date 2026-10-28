"use client";

import React from "react";
import type { UserReport } from "@/lib/api";
import { decisionPath, linear, signed, ticks, waterfallBars } from "@/lib/report-charts";
import { ChartFrame, DataTable, DirectionLegend, fit } from "./ChartFrame";

const pct = (v: number) => `${Math.round(v * 100)}%`;

/**
 * SHAP waterfall for one prediction: start from the model's average prediction (the base value),
 * add each factor's SHAP value in turn, strongest first, and end exactly at this prediction.
 */
export function ShapWaterfall({ waterfall }: { waterfall: NonNullable<UserReport["waterfall"]> }) {
  const bars = waterfallBars(waterfall.base, waterfall.steps, 8);
  const values = [waterfall.base, waterfall.output, ...bars.flatMap((b) => [b.start, b.end])];
  const lo = Math.max(0, Math.min(...values) - 0.05);
  const hi = Math.min(1, Math.max(...values) + 0.05);
  const row = 30;
  const top = 8;
  return (
    <ChartFrame
      id="shap-waterfall"
      testId="shap-waterfall"
      title="SHAP waterfall: how this prediction was built"
      caption={`Read top to bottom: start at the model's average prediction (${pct(waterfall.base)}), each bar adds one factor's push, and the last bar ends at this prediction (${pct(waterfall.output)}). The pushes add up exactly.`}
      legend={<DirectionLegend />}
      table={
        <DataTable
          head={["Factor", "Value", "SHAP", "Running total"]}
          rows={[
            ["Average prediction (start)", "", "", pct(waterfall.base)],
            ...bars.map((b) => [b.label, b.detail ?? "", signed(b.value), pct(b.end)]),
            ["This prediction", "", "", pct(waterfall.output)],
          ]}
        />
      }
    >
      {(width) => {
        const labelW = Math.min(230, Math.max(120, width * 0.38));
        const valueW = 64;
        const x = linear([lo, hi], [labelW, width - valueW]);
        const height = top + row * (bars.length + 2) + 24;
        const axisY = height - 20;
        return (
          <svg width={width} height={height} role="img" aria-label={`SHAP waterfall from ${pct(waterfall.base)} to ${pct(waterfall.output)}`}>
            {ticks(lo, hi, 5).map((t) => (
              <g key={t}>
                <line x1={x(t)} x2={x(t)} y1={top} y2={axisY} className="stroke-line" />
                <text x={x(t)} y={axisY + 14} textAnchor="middle" className="fill-subtle text-[10px] tabular-nums">
                  {pct(t)}
                </text>
              </g>
            ))}
            <text x={width - valueW} y={axisY + 14} textAnchor="end" className="fill-subtle text-[10px]" dx={valueW - 2}>
              P(correct)
            </text>
            {/* the start: the model's average prediction */}
            <Marker y={top + row / 2} x={x(waterfall.base)} label="Average prediction" value={pct(waterfall.base)} labelW={labelW} width={width} />
            {bars.map((b, i) => {
              const y = top + row * (i + 1);
              const up = b.value >= 0;
              const x0 = x(Math.min(b.start, b.end));
              const w = Math.max(1.5, Math.abs(x(b.end) - x(b.start)));
              return (
                <g key={b.key}>
                  <title>{`${b.label}${b.detail ? ` (${b.detail})` : ""}: ${signed(b.value)}`}</title>
                  <text x={labelW - 8} y={y + row / 2 - 1} textAnchor="end" className="fill-fg text-[12px]">
                    {fit(b.label, labelW - 12)}
                  </text>
                  {b.detail && (
                    <text x={labelW - 8} y={y + row / 2 + 11} textAnchor="end" className="fill-subtle text-[10px]">
                      {b.detail}
                    </text>
                  )}
                  <line x1={x(b.start)} x2={x(b.start)} y1={y - 2} y2={y + 4} className="stroke-line-strong" strokeDasharray="2 2" />
                  <rect x={x0} y={y + 6} width={w} height={row - 12} rx={3} fill={up ? "var(--viz-raise)" : "var(--viz-lower)"} />
                  <text x={width - 4} y={y + row / 2 + 4} textAnchor="end" className="fill-muted text-[11px] tabular-nums">
                    {up ? "▲" : "▼"} {signed(b.value)}
                  </text>
                </g>
              );
            })}
            <Marker
              y={top + row * (bars.length + 1) + row / 2}
              x={x(waterfall.output)}
              label="This prediction"
              value={pct(waterfall.output)}
              labelW={labelW}
              width={width}
              strong
            />
          </svg>
        );
      }}
    </ChartFrame>
  );
}

function Marker({ x, y, label, value, labelW, width, strong }: { x: number; y: number; label: string; value: string; labelW: number; width: number; strong?: boolean }) {
  return (
    <g>
      <text x={labelW - 8} y={y + 4} textAnchor="end" className={strong ? "fill-fg text-[12px] font-semibold" : "fill-muted text-[12px]"}>
        {label}
      </text>
      <circle cx={x} cy={y} r={strong ? 5 : 4} className={strong ? "fill-primary" : "fill-muted"} />
      <text x={width - 4} y={y + 4} textAnchor="end" className={strong ? "fill-fg text-[12px] font-semibold tabular-nums" : "fill-muted text-[11px] tabular-nums"}>
        {value}
      </text>
    </g>
  );
}

/**
 * SHAP decision plot over the learner's recent predictions: each line starts at the average
 * prediction at the bottom and moves left or right as each factor is added, least important
 * first, ending at the top at that prediction. Lines that end far right were predicted likely
 * to be right; the latest one is drawn heavier.
 */
export function DecisionPlot({ decision }: { decision: NonNullable<UserReport["decision"]> }) {
  const n = decision.features.length;
  const paths = decision.contributions.map((c) => decisionPath(decision.base, c));
  const all = paths.flat();
  const lo = Math.max(0, Math.min(...all) - 0.03);
  const hi = Math.min(1, Math.max(...all) + 0.03);
  const levelH = 22;
  return (
    <ChartFrame
      id="decision-plot"
      testId="decision-plot"
      title={`SHAP decision plot: the last ${decision.predictions.length} predictions`}
      caption="Each line is one past question. It starts at the average prediction at the bottom and moves right (more likely correct) or left as each factor is added, ending at the top at that question's prediction. The factor where lines bend most is the one that mattered most."
      legend={
        <>
          <span className="inline-flex items-center gap-1.5">
            <svg width="22" height="6" aria-hidden>
              <line x1="0" x2="22" y1="3" y2="3" stroke="var(--success)" strokeWidth="2" />
            </svg>
            answered correctly
          </span>
          <span className="inline-flex items-center gap-1.5">
            <svg width="22" height="6" aria-hidden>
              <line x1="0" x2="22" y1="3" y2="3" stroke="var(--text-muted)" strokeWidth="2" strokeDasharray="4 3" />
            </svg>
            answered incorrectly
          </span>
          <span>heavier line = the most recent</span>
        </>
      }
      table={
        <DataTable
          head={["Question", "When", "Prediction", "Outcome"]}
          rows={decision.predictions.map((p) => [
            p.concept,
            new Date(p.at).toLocaleDateString(),
            pct(p.p_correct),
            p.correct ? "correct" : "incorrect",
          ])}
        />
      }
    >
      {(width) => {
        const labelW = Math.min(220, Math.max(110, width * 0.36));
        const x = linear([lo, hi], [labelW, width - 12]);
        const top = 10;
        const plotH = levelH * n;
        const y = (level: number) => top + plotH - level * levelH; // level 0 = the base, at the bottom
        const axisY = top + plotH + 4;
        const last = decision.predictions.length - 1;
        return (
          <svg width={width} height={axisY + 26} role="img" aria-label="SHAP decision plot of recent predictions">
            {ticks(lo, hi, 5).map((t) => (
              <g key={t}>
                <line x1={x(t)} x2={x(t)} y1={top} y2={axisY} className="stroke-line" />
                <text x={x(t)} y={axisY + 14} textAnchor="middle" className="fill-subtle text-[10px] tabular-nums">
                  {pct(t)}
                </text>
              </g>
            ))}
            <line x1={x(decision.base)} x2={x(decision.base)} y1={top} y2={axisY} className="stroke-line-strong" strokeDasharray="3 3" />
            {/* factor names: the most important at the top */}
            {decision.labels.map((label, i) => (
              <text key={label} x={labelW - 8} y={y(n - i) + 4} textAnchor="end" className="fill-fg text-[11px]">
                {fit(label, labelW - 12)}
              </text>
            ))}
            {paths.map((path, k) => {
              const p = decision.predictions[k];
              const d = path.map((v, level) => `${level === 0 ? "M" : "L"}${x(v).toFixed(1)},${y(level).toFixed(1)}`).join(" ");
              return (
                <path
                  key={k}
                  d={d}
                  fill="none"
                  stroke={p.correct ? "var(--success)" : "var(--text-muted)"}
                  strokeDasharray={p.correct ? undefined : "4 3"}
                  strokeWidth={k === last ? 2.6 : 1.2}
                  opacity={k === last ? 1 : 0.5}
                >
                  <title>{`${p.concept}: predicted ${pct(p.p_correct)}, answered ${p.correct ? "correctly" : "incorrectly"}`}</title>
                </path>
              );
            })}
          </svg>
        );
      }}
    </ChartFrame>
  );
}
