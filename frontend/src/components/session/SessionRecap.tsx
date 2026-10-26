"use client";

import { motion } from "motion/react";
import React from "react";
import { masteryStep, recap, SessionAnswer, signedPoints } from "@/lib/moments";
import { Button, ButtonLink } from "../ui/Button";
import { ease } from "../ui/motion";

/** After every few answers: what this stretch covered, then keep going or take a break. */
export function SessionRecap({
  answers,
  names,
  name,
  onContinue,
}: {
  answers: SessionAnswer[];
  names: Record<string, string>;
  name: string;
  onContinue: () => void;
}) {
  const r = recap(answers);
  return (
    <motion.section
      data-testid="session-recap"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease }}
      className="space-y-5 rounded-xl border border-line bg-surface p-6 shadow-card"
      aria-labelledby="recap-title"
    >
      <div>
        <p className="label-caps">Session so far</p>
        <h2 id="recap-title" className="mt-1 text-lg font-semibold tracking-tight text-fg">
          {r.answered} questions done{name ? `, ${name}` : ""}.
        </h2>
        <p className="mt-0.5 text-sm text-muted">
          You got {r.correct} of {r.answered} right. Here is what moved.
        </p>
      </div>
      <ul className="divide-y divide-line rounded-lg border border-line">
        {r.concepts.map((c) => {
          const step = c.from !== null && c.to !== null ? masteryStep(c.from, c.to) : null;
          return (
            <li key={c.conceptId} className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm">
              <span className="min-w-0">
                <span className="block truncate text-fg">{names[c.conceptId] ?? c.conceptId}</span>
                <span className="text-xs text-subtle">
                  {c.answered} {c.answered === 1 ? "question" : "questions"}
                </span>
              </span>
              {step ? (
                <span className="flex flex-none items-center gap-2 text-xs tabular-nums text-muted">
                  {step.from}% → <span className="font-semibold text-fg">{step.to}%</span>
                  <span className="rounded-full bg-surface-2 px-1.5 py-px">{signedPoints(step.points)}</span>
                </span>
              ) : (
                <span className="text-xs text-subtle">placement</span>
              )}
            </li>
          );
        })}
      </ul>
      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <ButtonLink href="/dashboard" variant="secondary">
          Take a break
        </ButtonLink>
        <Button onClick={onContinue} autoFocus>
          Keep going <span aria-hidden>→</span>
        </Button>
      </div>
    </motion.section>
  );
}
