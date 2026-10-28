/**
 * Geometry for the report's hand-drawn SVG charts: scales, ticks, the SHAP waterfall, the decision
 * plot's paths, radar polygons and the diverging colour scale. Pure functions, unit-tested in
 * report-charts.test.ts, so the chart components only lay out what these compute.
 */

export interface Scale {
  (v: number): number;
  domain: [number, number];
}

/** A linear map from [d0, d1] onto [r0, r1]. */
export function linear([d0, d1]: [number, number], [r0, r1]: [number, number]): Scale {
  const span = d1 - d0 || 1;
  const f = ((v: number) => r0 + ((v - d0) / span) * (r1 - r0)) as Scale;
  f.domain = [d0, d1];
  return f;
}

/** About `count` round tick values covering [min, max] (steps of 1, 2 or 5 x 10^k). */
export function ticks(min: number, max: number, count = 5): number[] {
  if (!(max > min)) return [min];
  const raw = (max - min) / count;
  const power = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 5, 10].map((m) => m * power).find((s) => s >= raw) ?? raw;
  const out: number[] = [];
  for (let v = Math.ceil(min / step) * step; v <= max + step * 1e-9; v += step) {
    out.push(Number(v.toFixed(10)));
  }
  return out;
}

/** A symmetric domain around 0 that holds every value, for diverging bar charts. */
export function symmetricDomain(values: number[], floor = 1e-9): [number, number] {
  const m = Math.max(floor, ...values.map(Math.abs));
  return [-m, m];
}

export interface WaterfallBar {
  key: string;
  label: string;
  detail?: string;
  start: number;
  end: number;
  value: number;
}

/**
 * SHAP waterfall: start at the base value, add each factor in turn (strongest first, as given),
 * and fold whatever is left after `max` factors into one "other factors" bar, so the last bar
 * always ends exactly at the prediction.
 */
export function waterfallBars(
  base: number,
  steps: { name: string; label: string; display?: string; value: number }[],
  max = 8
): WaterfallBar[] {
  const shown = steps.slice(0, max);
  const rest = steps.slice(max);
  const bars: WaterfallBar[] = [];
  let at = base;
  for (const s of shown) {
    bars.push({ key: s.name, label: s.label, detail: s.display, start: at, end: at + s.value, value: s.value });
    at += s.value;
  }
  if (rest.length) {
    const value = rest.reduce((sum, s) => sum + s.value, 0);
    bars.push({ key: "__other", label: `${rest.length} other factors`, start: at, end: at + value, value });
  }
  return bars;
}

/**
 * SHAP decision plot: a prediction's path from the base value, adding factors from the least to
 * the most important, so the line ends at the top at the prediction itself. `contributions` are
 * in most-important-first order; returns the cumulative x for each level, bottom (base) to top.
 */
export function decisionPath(base: number, contributions: number[]): number[] {
  const path = [base];
  for (let i = contributions.length - 1; i >= 0; i--) path.push(path[path.length - 1] + contributions[i]);
  return path;
}

/** Points of a radar polygon: one value in [0, 1] per axis, axis 0 straight up, clockwise. */
export function radarPoints(values: number[], radius: number, cx: number, cy: number): [number, number][] {
  return values.map((v, i) => {
    const angle = -Math.PI / 2 + (2 * Math.PI * i) / values.length;
    const r = Math.max(0, Math.min(1, v)) * radius;
    return [cx + r * Math.cos(angle), cy + r * Math.sin(angle)];
  });
}

/** Where to put an axis label around a radar: just outside the ring, anchored away from it. */
export function radarLabel(i: number, n: number, radius: number, cx: number, cy: number) {
  const angle = -Math.PI / 2 + (2 * Math.PI * i) / n;
  const x = cx + (radius + 14) * Math.cos(angle);
  const y = cy + (radius + 14) * Math.sin(angle);
  const c = Math.cos(angle);
  const anchor: "start" | "middle" | "end" = Math.abs(c) < 0.2 ? "middle" : c > 0 ? "start" : "end";
  return { x, y, anchor };
}

/**
 * Diverging heat colour: blue raises, orange lowers, stronger = more opaque. Returns the CSS
 * colour variable and an opacity in [0.06, 1], so tiny values stay visible as a faint tint.
 */
export function heat(value: number, max: number): { color: string; opacity: number } {
  const strength = max > 0 ? Math.min(1, Math.abs(value) / max) : 0;
  return {
    color: value >= 0 ? "var(--viz-raise)" : "var(--viz-lower)",
    opacity: 0.06 + 0.94 * strength,
  };
}

/** Deterministic vertical offsets for a beeswarm row, so points with similar x don't overlap. */
export function swarm(xs: number[], radius: number, maxOffset: number): number[] {
  const placed: { x: number; y: number }[] = [];
  const order = xs.map((x, i) => [x, i] as const).sort((a, b) => a[0] - b[0]);
  const ys = new Array<number>(xs.length).fill(0);
  for (const [x, i] of order) {
    let y = 0;
    for (let k = 0; k < 64; k++) {
      y = (k % 2 === 0 ? 1 : -1) * Math.ceil(k / 2) * radius * 2;
      if (Math.abs(y) > maxOffset) {
        y = Math.max(-maxOffset, Math.min(maxOffset, y));
        break;
      }
      if (placed.every((p) => Math.hypot(p.x - x, p.y - y) >= radius * 1.8)) break;
    }
    placed.push({ x, y });
    ys[i] = y;
  }
  return ys;
}

/** "+4.1 pts" / "−0.42": contributions in percentage points (probabilities) or raw (logits). */
export function signed(v: number | null | undefined, unit: "pts" | "logit" = "pts"): string {
  if (v === null || v === undefined) return "—";
  const sign = v > 0 ? "+" : v < 0 ? "−" : "±";
  return unit === "pts" ? `${sign}${Math.abs(v * 100).toFixed(1)} pts` : `${sign}${Math.abs(v).toFixed(2)}`;
}
