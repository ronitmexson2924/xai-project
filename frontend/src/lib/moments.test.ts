// Unit tests for the learner-facing copy: node --test (npm run test:unit)
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  daysAgo,
  describeChange,
  firstName,
  flaggedMisconception,
  masteryStep,
  pathStep,
  recap,
  resultMoment,
  secondPersonSummary,
  signedPoints,
  thinkingLine,
  timeOfDay,
} from "./moments.ts";

test("beat the prediction: right answer against a shown chance below 50%", () => {
  const m = resultMoment({ correct: true, pCorrect: 0.44 });
  assert.equal(m.kind, "beat");
  assert.equal(m.detail, "The model gave you a 44% chance, and you proved it wrong.");
});

test("a 50% prediction is a coin flip, not long odds", () => {
  assert.equal(resultMoment({ correct: true, pCorrect: 0.5 }).kind, "correct");
  // 0.497 is shown as 50% everywhere else, so it is not "beaten" either
  assert.equal(resultMoment({ correct: true, pCorrect: 0.497 }).kind, "correct");
  assert.equal(resultMoment({ correct: true, pCorrect: 0.494 }).kind, "beat");
});

test("a wrong answer is never 'beating' anything, whatever the prediction", () => {
  for (const p of [0.1, 0.44, 0.5, 0.9, null]) {
    const m = resultMoment({ correct: false, pCorrect: p });
    assert.equal(m.kind, "incorrect");
    assert.doesNotMatch(`${m.title} ${m.detail}`, /beat|prediction|%/);
  }
});

test("without a prediction, a right answer is just correct", () => {
  assert.equal(resultMoment({ correct: true, pCorrect: null }).kind, "correct");
});

test("correct-answer copy rotates, sincerely and without exclamation marks", () => {
  const titles = new Set([0, 1, 2, 3, 4].map((turn) => resultMoment({ correct: true, pCorrect: 0.8, turn }).title));
  assert.ok(titles.size >= 3);
  for (const t of titles) assert.match(t, /^(Correct|Right)/);
  for (const t of titles) assert.doesNotMatch(t, /!/);
});

test("misconception copy only when the learner model flagged one", () => {
  assert.match(resultMoment({ correct: false, pCorrect: 0.3, misconception: true }).detail!, /mix-up\. The explanation below/);
  assert.match(resultMoment({ correct: false, pCorrect: 0.3, example: "above" }).detail!, /explanation above/);
  assert.doesNotMatch(resultMoment({ correct: false, pCorrect: 0.3 }).detail!, /mix-up/);
  assert.equal(flaggedMisconception(["misconception flagged: base-case-missing"]), true);
  assert.equal(flaggedMisconception(["misconceptions cleared: x"]), false);
  assert.equal(flaggedMisconception(undefined), false);
});

const insight = {
  p_correct: 0.553,
  attributions: [
    {
      method: "shap",
      title: "SHAP",
      about: "",
      unit: "probability",
      base: 0.73,
      output: 0.553,
      fidelity: null,
      contributions: { mastery: -0.103, overall_accuracy: -0.041, days_since_practice: -0.037, prereq_mean: 0.014, attempts: 0.004 },
    },
  ],
};

test("second-person summary: same number, same top factors as the backend's", () => {
  const s = secondPersonSummary(insight);
  assert.equal(
    s,
    "Before this question, the model gave you a 55% chance of getting it right. What helped: your mastery of its prerequisites. What held it back: your mastery of this concept and your accuracy across all concepts."
  );
  assert.doesNotMatch(s, /how many questions/); // +0.4 pts is under the backend's 0.5-pt cut-off
});

test("second-person summary with nothing past the cut-off", () => {
  const flat = { ...insight, attributions: [{ ...insight.attributions[0], contributions: { mastery: 0.001 } }] };
  assert.match(secondPersonSummary(flat), /Nothing moved it far/);
  assert.equal(secondPersonSummary({ p_correct: 0.3, attributions: [] }), "Before this question, the model gave you a 30% chance of getting it right.");
});

test("recency never reads 'were 0.0 days (now never practised)'", () => {
  const c = { name: "days_since_practice", label: "Days since this concept was practised", now: "never practised", then: "0.0 days" };
  assert.equal(describeChange(c), "you had practised it today (now: never)");
  assert.equal(describeChange({ ...c, then: "2.5 days", now: "9.0 days" }), "you had last practised it 2.5 days ago (now: 9.0 days ago)");
  assert.deepEqual(pathStep(c), { action: "Practise it more recently", now: "never", target: "today" });
});

test("other changes keep the backend's values verbatim", () => {
  const c = { name: "overall_accuracy", label: "Accuracy across all concepts", now: "50%", then: "0%" };
  assert.equal(describeChange(c), "accuracy across all concepts were 0% (now 50%)");
  assert.deepEqual(pathStep({ ...c, now: "13%", then: "62%", name: "mastery" }), { action: "Raise your mastery of this concept", now: "13%", target: "62%" });
  assert.equal(describeChange({ name: "misconception", label: "A known misconception is flagged", now: "yes", then: "no" }), "the flagged misconception were cleared");
});

test("mastery step uses the shown, rounded percentages", () => {
  assert.deepEqual(masteryStep(0.128, 0.394), { from: 13, to: 39, points: 26 });
  assert.equal(signedPoints(26), "+26 pts");
  assert.equal(signedPoints(-4), "−4 pts");
  assert.equal(signedPoints(0), "±0 pts");
});

test("names, greetings and dates", () => {
  assert.equal(firstName("  Ada  Lovelace "), "Ada");
  assert.equal(firstName(""), "");
  assert.equal(firstName(undefined), "");
  assert.equal(timeOfDay(8), "Good morning");
  assert.equal(timeOfDay(13), "Good afternoon");
  assert.equal(timeOfDay(23), "Good evening");
  assert.equal(timeOfDay(3), "Good evening");
  const now = new Date(2026, 9, 26, 10);
  assert.equal(daysAgo(new Date(2026, 9, 26, 8).toISOString(), now), "today");
  assert.equal(daysAgo(new Date(2026, 9, 25, 22).toISOString(), now), "yesterday");
  assert.equal(daysAgo(new Date(2026, 9, 21, 9).toISOString(), now), "5 days ago");
  assert.equal(daysAgo(new Date(2026, 10, 2).toISOString(), now), null); // future-dated data
});

test("thinking line uses only what is known", () => {
  assert.equal(thinkingLine({ name: "Maya" }), "Looking at what you know so far, Maya…");
  assert.equal(thinkingLine({ name: "" }), "Looking at what you know so far…");
  assert.equal(thinkingLine({ name: "Maya", lastConcept: "Recursion", lastCorrect: true }), "Building on your answer about Recursion…");
  assert.equal(thinkingLine({ name: "Maya", lastConcept: "Recursion", lastCorrect: false }), "Taking your answer about Recursion into account…");
});

test("recap groups answers by concept from the attempts' own deltas", () => {
  const r = recap([
    { conceptId: "a", correct: false, before: 0.2, after: 0.15 },
    { conceptId: "b", correct: true, before: null, after: null },
    { conceptId: "a", correct: true, before: 0.15, after: 0.4 },
  ]);
  assert.equal(r.answered, 3);
  assert.equal(r.correct, 2);
  assert.deepEqual(r.concepts, [
    { conceptId: "a", answered: 2, from: 0.2, to: 0.4 },
    { conceptId: "b", answered: 1, from: null, to: null },
  ]);
});

test("the highlighter keeps every character and finds keywords, strings, numbers, comments", async () => {
  const { highlightLine } = await import("./highlight.ts");
  const line = `    return f"{n}!" if n > 10 else total(a[1:])  # recurse`;
  const tokens = highlightLine(line);
  assert.equal(tokens.map((t) => t.text).join(""), line);
  const kinds = (k: string) => tokens.filter((t) => t.kind === k).map((t) => t.text.trim());
  assert.deepEqual(kinds("keyword"), ["return", "if", "else"]);
  assert.deepEqual(kinds("string"), [`f"{n}!"`]);
  assert.deepEqual(kinds("number"), ["10", "1"]);
  assert.deepEqual(kinds("comment"), ["# recurse"]);
  assert.deepEqual(highlightLine("best = a[0]").map((t) => t.kind), ["plain", "number", "plain"]);
  assert.deepEqual(highlightLine("ifx = 'it''s'"), [{ kind: "plain", text: "ifx = " }, { kind: "string", text: "'it''s'" }]);
});
