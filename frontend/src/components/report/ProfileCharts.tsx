"use client";

import React from "react";
import type { GlobalAttributions, RadarAxis, UserReport } from "@/lib/api";
import { heat, linear, radarLabel, radarPoints, signed, swarm, symmetricDomain, ticks } from "@/lib/report-charts";
import { ChartFrame, DataTable, DirectionLegend, fit } from "./ChartFrame";

/**
 * A radar ("spider") chart of values in [0, 1]: one axis per trait or cluster, the filled shape
 * is this learner's profile. Rings mark 25%, 50%, 75% and 100%.
 */
export function Radar({
  id,
  title,
  caption,
  axes,
  format = (v: number) => `${Math.round(v * 100)}%`,
}: {
  id: string;
  title: string;
  caption: string;
  axes: RadarAxis[];
  format?: (v: number) => string;
}) {
  return (
    <ChartFrame
      id={id}
      testId={id}
      title={title}
      caption={caption}
      table={<DataTable head={["Axis", "Value", "Detail"]} rows={axes.map((a) => [a.label, format(a.value), a.detail])} />}
    >
      {(width) => {
        const size = Math.min(width, 380);
        const labelRoom = size < 320 ? 64 : 84;
        const radius = size / 2 - labelRoom;
        const cx = width / 2;
        const cy = size / 2;
        const n = axes.length;
        const ring = (f: number) =>
          radarPoints(new Array(n).fill(f), radius, cx, cy)
            .map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`)
            .join(" ");
        const shape = radarPoints(axes.map((a) => a.value), radius, cx, cy);
        return (
          <svg width={width} height={size} role="img" aria-label={`${title}: ${axes.map((a) => `${a.label} ${format(a.value)}`).join(", ")}`}>
            {[0.25, 0.5, 0.75, 1].map((f) => (
              <polygon key={f} points={ring(f)} fill="none" className={f === 1 ? "stroke-line-strong" : "stroke-line"} />
            ))}
            {radarPoints(new Array(n).fill(1), radius, cx, cy).map(([x, y], i) => (
              <line key={i} x1={cx} y1={cy} x2={x} y2={y} className="stroke-line" />
            ))}
            <polygon
              points={shape.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ")}
              fill="var(--primary)"
              fillOpacity={0.16}
              stroke="var(--primary)"
              strokeWidth={2}
            />
            {shape.map(([x, y], i) => (
              <circle key={i} cx={x} cy={y} r={3.5} fill="var(--primary)">
                <title>{`${axes[i].label}: ${format(axes[i].value)} (${axes[i].detail})`}</title>
              </circle>
            ))}
            {axes.map((a, i) => {
              const { x, y, anchor } = radarLabel(i, n, radius, cx, cy);
              return (
                <text key={a.key} x={x} y={y} textAnchor={anchor} dominantBaseline="middle" className="fill-fg text-[11px]">
                  {/* room to the card's edge for side labels, the ring's width for top and bottom */}
                  <tspan>{fit(a.label, anchor === "middle" ? radius * 1.6 : (width - size) / 2 + labelRoom - 16, 5.6)}</tspan>
                  <tspan x={x} dy="13" className="fill-subtle text-[10px] tabular-nums">
                    {format(a.value)}
                  </tspan>
                </text>
              );
            })}
          </svg>
        );
      }}
    </ChartFrame>
  );
}

/**
 * LRP relevance heatmap over the learner's recent predictions: rows are factors (most relevant on
 * average at the top), columns are past questions in time order, and each cell is how much that
 * factor contributed to that prediction according to the network's own weights.
 */
export function LrpHeatmap({ heatmap }: { heatmap: NonNullable<UserReport["heatmap"]> }) {
  const n = heatmap.predictions.length;
  const max = Math.max(1e-9, ...heatmap.values.flat().map(Math.abs));
  return (
    <ChartFrame
      id="lrp-heatmap"
      testId="lrp-heatmap"
      title={`LRP relevance heatmap: the last ${n} predictions`}
      caption="Each column is one past question (oldest left), each row a factor. Blue cells raised that prediction and orange cells lowered it, according to the network's own weights (layer-wise relevance propagation, in log-odds). Darker means stronger. ✓ and ✕ above each column show how the question was answered."
      legend={<DirectionLegend raises="raised the prediction" lowers="lowered it" />}
      table={
        <DataTable
          head={["Factor", ...heatmap.predictions.map((_, i) => `Q${i + 1}`)]}
          rows={heatmap.labels.map((label, r) => [label, ...heatmap.values[r].map((v) => signed(v, "logit"))])}
        />
      }
    >
      {(width) => {
        const labelW = Math.min(210, Math.max(100, width * 0.34));
        const cell = Math.max(8, Math.min(30, (width - labelW - 4) / n));
        const rowH = 20;
        const top = 22;
        return (
          <svg width={width} height={top + heatmap.labels.length * rowH + 4} role="img" aria-label="LRP relevance per factor and recent question">
            {heatmap.predictions.map((p, c) => (
              <text key={c} x={labelW + c * cell + cell / 2} y={14} textAnchor="middle" className={p.correct ? "fill-success text-[10px]" : "fill-subtle text-[10px]"}>
                {p.correct ? "✓" : "✕"}
              </text>
            ))}
            {heatmap.labels.map((label, r) => (
              <g key={label}>
                <text x={labelW - 8} y={top + r * rowH + rowH / 2 + 4} textAnchor="end" className="fill-fg text-[11px]">
                  {fit(label, labelW - 12)}
                </text>
                {heatmap.values[r].map((v, c) => {
                  const h = heat(v, max);
                  const p = heatmap.predictions[c];
                  return (
                    <rect key={c} x={labelW + c * cell + 0.5} y={top + r * rowH + 0.5} width={cell - 1} height={rowH - 1} rx={2} fill={h.color} fillOpacity={h.opacity}>
                      <title>{`${label}, question ${c + 1} (${p.concept}): ${signed(v, "logit")}`}</title>
                    </rect>
                  );
                })}
              </g>
            ))}
          </svg>
        );
      }}
    </ChartFrame>
  );
}

/**
 * Admins only: SHAP across many learners' recent predictions, one row per factor. Each dot is one
 * prediction (no learner is identified); its position is the factor's push, its shade the
 * factor's value, from light (low) to dark (high).
 */
export function Beeswarm({ data }: { data: GlobalAttributions }) {
  const domain = symmetricDomain(data.features.flatMap((f) => f.points.map((p) => p.shap)));
  return (
    <ChartFrame
      id="beeswarm"
      testId="beeswarm"
      title={`SHAP beeswarm: ${data.predictions} recent predictions from ${data.learners} learners`}
      caption="Each dot is one prediction. Its horizontal position is how much the factor pushed that prediction up (right) or down (left), in percentage points; its shade is the factor's value for that learner, light for low and dark for high. Factors are ordered by average impact."
      legend={
        <span className="inline-flex items-center gap-2">
          factor value: low
          <span className="h-2.5 w-24 rounded-full" style={{ background: "linear-gradient(to right, color-mix(in oklab, var(--primary) 18%, var(--surface)), var(--primary))" }} aria-hidden />
          high
        </span>
      }
      table={
        <DataTable
          head={["Factor", "Mean |SHAP|", "Predictions"]}
          rows={data.features.map((f) => [f.label, signed(f.mean_abs_shap).replace("+", ""), String(f.points.length)])}
        />
      }
    >
      {(width) => {
        const labelW = Math.min(220, Math.max(110, width * 0.32));
        const x = linear(domain, [labelW + 8, width - 10]);
        const rowH = 30;
        const r = 2.6;
        const height = data.features.length * rowH + 24;
        return (
          <svg width={width} height={height} role="img" aria-label="SHAP beeswarm across learners">
            <line x1={x(0)} x2={x(0)} y1={0} y2={data.features.length * rowH} className="stroke-line-strong" />
            {data.features.map((f, i) => {
              const cy = i * rowH + rowH / 2;
              const xs = f.points.map((p) => x(p.shap));
              const ys = swarm(xs, r, rowH / 2 - r);
              return (
                <g key={f.name}>
                  <text x={labelW - 4} y={cy + 4} textAnchor="end" className="fill-fg text-[11px]">
                    {fit(f.label, labelW - 8)}
                  </text>
                  {f.points.map((p, k) => (
                    <circle
                      key={k}
                      cx={xs[k]}
                      cy={cy + ys[k]}
                      r={r}
                      fill={`color-mix(in oklab, var(--primary) ${Math.round(18 + 82 * p.position)}%, var(--surface))`}
                    />
                  ))}
                </g>
              );
            })}
            {ticks(domain[0], domain[1], 4).map((t) => (
              <text key={t} x={x(t)} y={height - 6} textAnchor="middle" className="fill-subtle text-[10px] tabular-nums">
                {signed(t).replace(" pts", "")}
              </text>
            ))}
          </svg>
        );
      }}
    </ChartFrame>
  );
}

