// Unit tests for the report's chart geometry: node --test (npm run test:unit)
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  decisionPath,
  heat,
  linear,
  radarPoints,
  signed,
  swarm,
  symmetricDomain,
  ticks,
  waterfallBars,
} from "./report-charts.ts";

test("linear scales map domain onto range", () => {
  const x = linear([0, 1], [10, 110]);
  assert.equal(x(0), 10);
  assert.equal(x(0.5), 60);
  assert.equal(x(1), 110);
  assert.deepEqual(x.domain, [0, 1]);
});

test("ticks are round numbers covering the range", () => {
  assert.deepEqual(ticks(0, 1, 5), [0, 0.2, 0.4, 0.6, 0.8, 1]);
  assert.deepEqual(ticks(-0.3, 0.3, 4), [-0.2, 0, 0.2]);
  assert.deepEqual(ticks(2, 2), [2]);
});

test("a symmetric domain holds every value around zero", () => {
  assert.deepEqual(symmetricDomain([0.1, -0.4, 0.2]), [-0.4, 0.4]);
  assert.deepEqual(symmetricDomain([]), [-1e-9, 1e-9]);
});

test("the waterfall starts at the base and its last bar ends at the prediction", () => {
  const steps = [0.2, -0.1, 0.05, -0.02, 0.01].map((value, i) => ({ name: `f${i}`, label: `F${i}`, value }));
  const bars = waterfallBars(0.5, steps, 3);
  assert.equal(bars.length, 4);
  assert.equal(bars[0].start, 0.5);
  assert.equal(bars[3].label, "2 other factors");
  assert.ok(Math.abs(bars.at(-1)!.end - (0.5 + 0.2 - 0.1 + 0.05 - 0.02 + 0.01)) < 1e-12);
  for (let i = 1; i < bars.length; i++) assert.equal(bars[i].start, bars[i - 1].end);
});

test("a decision path adds the least important factor first and ends at the prediction", () => {
  // most important first: 0.3, then 0.1, then -0.05
  const path = decisionPath(0.5, [0.3, 0.1, -0.05]);
  assert.deepEqual(
    path.map((v) => Number(v.toFixed(10))),
    [0.5, 0.45, 0.55, 0.85]
  );
});

test("radar points start at the top and go clockwise, clamped to the ring", () => {
  const [top, right] = radarPoints([1, 2, 0, 0], 10, 0, 0);
  assert.ok(Math.abs(top[0]) < 1e-9 && Math.abs(top[1] + 10) < 1e-9);
  assert.ok(Math.abs(right[0] - 10) < 1e-9 && Math.abs(right[1]) < 1e-9); // 2 is clamped to 1
});

test("heat colours: blue raises, orange lowers, stronger is more opaque", () => {
  assert.equal(heat(0.5, 1).color, "var(--viz-raise)");
  assert.equal(heat(-0.5, 1).color, "var(--viz-lower)");
  assert.ok(heat(1, 1).opacity > heat(0.1, 1).opacity);
  assert.equal(heat(0, 0).opacity, 0.06);
});

test("the beeswarm separates points that would overlap and keeps them in bounds", () => {
  const ys = swarm([0, 0, 0, 0, 5], 2, 6);
  assert.equal(ys[4], 0); // nothing near it
  assert.equal(new Set(ys.slice(0, 4)).size, 4); // the four at x = 0 are spread apart
  assert.ok(ys.every((y) => Math.abs(y) <= 6));
});

test("signed values", () => {
  assert.equal(signed(0.041), "+4.1 pts");
  assert.equal(signed(-0.42, "logit"), "−0.42");
  assert.equal(signed(null), "—");
});
