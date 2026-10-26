/**
 * Learner-facing copy built from data the app already has. Every number shown here is one the
 * backend returned (rounded the same way the rest of the UI rounds it); nothing is computed anew
 * and nothing is invented. Pure functions, so they are unit-tested (moments.test.ts).
 */
import type { CounterfactualChange, ModelInsight } from "./api";

/** "Ada Lovelace" -> "Ada". Empty when there is no usable name. */
export function firstName(displayName: string | null | undefined): string {
  return (displayName ?? "").trim().split(/\s+/)[0]?.slice(0, 40) ?? "";
}

export function timeOfDay(hour: number): string {
  return hour >= 5 && hour < 12 ? "Good morning" : hour >= 12 && hour < 18 ? "Good afternoon" : "Good evening";
}

/** A stable hue for the avatar, so a person's colour is the same on every visit. */
export function avatarHue(name: string): number {
  let h = 0;
  for (const ch of name.trim().toLowerCase()) h = (h * 31 + ch.codePointAt(0)!) % 360;
  return h;
}

/** "today", "yesterday", "3 days ago"; null for a time in the future (clock skew, seeded data). */
export function daysAgo(iso: string, now: Date = new Date()): string | null {
  const then = new Date(iso);
  if (Number.isNaN(then.getTime()) || then.getTime() > now.getTime() + 60_000) return null;
  const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((startOfDay(now) - startOfDay(then)) / 86_400_000);
  return days <= 0 ? "today" : days === 1 ? "yesterday" : `${days} days ago`;
}

export const pct = (p: number) => Math.round(p * 100);

// --- the moment after an answer --------------------------------------------------------------

export type MomentKind = "beat" | "correct" | "incorrect";

export interface Moment {
  kind: MomentKind;
  title: string;
  detail: string | null;
}

const CORRECT = ["Correct, nice reasoning.", "Correct. That’s the idea.", "Right, well worked out.", "Correct, you’ve got it."];

/**
 * What to say after an answer. "Beat the prediction" only when the answer was right *and* the
 * model's shown chance was below 50% (a shown 50% is a coin flip, not long odds). `pCorrect` is
 * the model's prediction made before the answer, or null when it is not available.
 */
export function resultMoment({
  correct,
  pCorrect,
  misconception = false,
  turn = 0,
  example = "below",
}: {
  correct: boolean;
  pCorrect: number | null;
  misconception?: boolean;
  turn?: number;
  /** where the step's explanation sits on the page relative to this message */
  example?: "above" | "below";
}): Moment {
  if (!correct) {
    return {
      kind: "incorrect",
      title: "Not quite, and that’s useful to know.",
      detail: misconception
        ? `This answer usually comes from a common mix-up. The explanation ${example} untangles it.`
        : `Have another look at the explanation ${example}; it walks through the idea step by step.`,
    };
  }
  if (pCorrect !== null && pct(pCorrect) < 50) {
    return {
      kind: "beat",
      title: "You beat the prediction.",
      detail: `The model gave you a ${pct(pCorrect)}% chance, and you proved it wrong.`,
    };
  }
  return { kind: "correct", title: CORRECT[Math.abs(turn) % CORRECT.length], detail: null };
}

/** True when the answer flagged a misconception (the learner model's own note, not a guess). */
export function flaggedMisconception(notes: readonly string[] | undefined): boolean {
  return (notes ?? []).some((n) => n.startsWith("misconception flagged: "));
}

/** The mastery change from an answer, in the whole percentages the UI shows. */
export function masteryStep(before: number, after: number): { from: number; to: number; points: number } {
  const from = pct(before);
  const to = pct(after);
  return { from, to, points: to - from };
}

export function signedPoints(points: number): string {
  return `${points > 0 ? "+" : points < 0 ? "−" : "±"}${Math.abs(points)} pts`;
}

// --- while the next step loads ------------------------------------------------------------------

export function thinkingLine({
  name,
  lastConcept,
  lastCorrect,
}: {
  name: string;
  lastConcept?: string | null;
  lastCorrect?: boolean | null;
}): string {
  const you = name ? `, ${name}` : "";
  if (lastConcept && lastCorrect === true) return `Building on your answer about ${lastConcept}…`;
  if (lastConcept && lastCorrect === false) return `Taking your answer about ${lastConcept} into account…`;
  return `Looking at what you know so far${you}…`;
}

// --- the model panel, in the second person ---------------------------------------------------

/** How each factor reads when it is about "you". */
export const YOUR_FACTOR: Record<string, string> = {
  mastery: "your mastery of this concept",
  prereq_mean: "your mastery of its prerequisites",
  prereq_min: "your weakest prerequisite",
  attempts: "how many questions you’ve answered here",
  recent_accuracy: "your recent accuracy here",
  overall_accuracy: "your accuracy across all concepts",
  streak: "your current streak here",
  misconception: "a flagged misconception",
  item_difficulty: "the question’s difficulty",
  guess_rate: "the chance of guessing it",
  days_since_practice: "how long since you practised it",
  self_efficacy: "your self-efficacy answers",
  persistence: "your persistence answers",
};

const MIN_POINTS = 0.005; // the backend summary's own cut-off for a factor worth naming

function joinAnd(parts: string[]): string {
  return parts.length <= 1 ? (parts[0] ?? "") : `${parts.slice(0, -1).join(", ")} and ${parts.at(-1)}`;
}

/**
 * The backend's one-line summary, retold to the learner: the same SHAP contributions, the same top
 * two factors each way and the same cut-off, only worded as "you".
 */
export function secondPersonSummary(insight: Pick<ModelInsight, "p_correct" | "attributions">): string {
  const shap = insight.attributions.find((a) => a.method === "shap");
  const lead = `Before this question, the model gave you a ${pct(insight.p_correct)}% chance of getting it right.`;
  if (!shap) return lead;
  const ranked = Object.entries(shap.contributions).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
  const name = (k: string) => YOUR_FACTOR[k] ?? k;
  const up = ranked.filter(([, v]) => v > MIN_POINTS).slice(0, 2).map(([k]) => name(k));
  const down = ranked.filter(([, v]) => v < -MIN_POINTS).slice(0, 2).map(([k]) => name(k));
  const parts = [lead];
  if (up.length) parts.push(`What helped: ${joinAnd(up)}.`);
  if (down.length) parts.push(`What held it back: ${joinAnd(down)}.`);
  if (!up.length && !down.length) parts.push("Nothing moved it far from an average learner’s.");
  return parts.join(" ");
}

/** What each method's starting point is, verified against backend/app/ml/explain.py. */
export const BASELINE_NOTE: Record<string, string> = {
  shap: "SHAP starts from the model’s average prediction over its reference learners, then adds each factor’s share.",
  lime: "LIME fits a straight line to the model around you; it starts from that line’s intercept, so its starting point differs from SHAP’s.",
  lrp: "LRP works in log-odds and starts from what the network’s biases account for, relative to an average learner.",
};

/** "0.0 days" -> "today"; "2.5 days" -> "2.5 days ago"; "never practised" -> "never". */
function practisedWhen(display: string): string {
  if (display === "never practised") return "never";
  const days = Number.parseFloat(display);
  if (Number.isNaN(days)) return display;
  if (days < 0.05) return "today";
  return `${display} ago`;
}

/**
 * One counterfactual change as text. The plain voice keeps the panel's existing sentence shape
 * ("accuracy across all concepts were 0% (now 50%)"); recency is worded as a time, so it never
 * reads "were 0.0 days (now never practised)".
 */
export function describeChange(c: Pick<CounterfactualChange, "name" | "label" | "now" | "then">): string {
  if (c.name === "days_since_practice") {
    const then = practisedWhen(c.then);
    const now = practisedWhen(c.now);
    return then === "today"
      ? `you had practised it today (now: ${now})`
      : `you had last practised it ${then} (now: ${now})`;
  }
  if (c.name === "misconception") {
    return c.then === "no" ? "the flagged misconception were cleared" : `${c.label.toLowerCase()} were ${c.then} (now ${c.now})`;
  }
  return `${c.label.toLowerCase()} were ${c.then} (now ${c.now})`;
}

/** The same change as a step on "your path": an action, and where it goes from and to. */
export function pathStep(c: Pick<CounterfactualChange, "name" | "label" | "now" | "then">): { action: string; now: string; target: string } {
  const ACTION: Record<string, string> = {
    mastery: "Raise your mastery of this concept",
    prereq_mean: "Strengthen its prerequisites",
    prereq_min: "Strengthen your weakest prerequisite",
    attempts: "Answer more questions on this concept",
    recent_accuracy: "Get more of your recent answers here right",
    overall_accuracy: "Raise your accuracy across concepts",
    streak: "Build a streak on this concept",
    misconception: "Clear the flagged misconception",
    days_since_practice: "Practise it more recently",
  };
  if (c.name === "days_since_practice") {
    return { action: ACTION[c.name], now: practisedWhen(c.now), target: practisedWhen(c.then) };
  }
  return { action: ACTION[c.name] ?? c.label, now: c.now, target: c.then };
}

// --- the session ---------------------------------------------------------------------------

export interface SessionAnswer {
  conceptId: string;
  correct: boolean;
  /** mastery of the answered concept before and after, from the attempt's own delta */
  before: number | null;
  after: number | null;
}

/** Per concept: how many answered, how many right, mastery from the first "before" to the last "after". */
export function recap(answers: readonly SessionAnswer[]): {
  answered: number;
  correct: number;
  concepts: { conceptId: string; answered: number; from: number | null; to: number | null }[];
} {
  const byConcept = new Map<string, { conceptId: string; answered: number; from: number | null; to: number | null }>();
  for (const a of answers) {
    const row = byConcept.get(a.conceptId) ?? { conceptId: a.conceptId, answered: 0, from: a.before, to: null };
    row.answered += 1;
    if (row.from === null) row.from = a.before;
    if (a.after !== null) row.to = a.after;
    byConcept.set(a.conceptId, row);
  }
  return {
    answered: answers.length,
    correct: answers.filter((a) => a.correct).length,
    concepts: [...byConcept.values()],
  };
}
