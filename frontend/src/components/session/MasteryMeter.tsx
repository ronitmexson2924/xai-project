"use client";

import { animate, motion, useMotionValue, useReducedMotion, useTransform } from "motion/react";
import React, { useEffect } from "react";
import { FRONTIER_PREREQ_MIN, MASTERED, PREREQ_WEAK } from "@/lib/mastery";
import { masteryStep, signedPoints } from "@/lib/moments";
import { cn } from "../ui/cn";

const TICKS = [
  { at: PREREQ_WEAK, label: "Getting there" },
  { at: FRONTIER_PREREQ_MIN, label: "Ready to move on" },
  { at: MASTERED, label: "Mastered" },
];

/**
 * The answer's mastery change, drawn: the bar fills from the old estimate to the new one over
 * 700 ms while the number counts up. Ticks mark the planner's own thresholds (lib/mastery.ts).
 * The numbers are the attempt's delta, rounded as everywhere else.
 */
export function MasteryMeter({ concept, before, after }: { concept: string; before: number; after: number }) {
  const reduce = useReducedMotion();
  const { from, to, points } = masteryStep(before, after);
  const value = useMotionValue(reduce ? to : from);
  const shown = useTransform(value, (v) => `${Math.round(v)}%`);

  useEffect(() => {
    if (reduce) {
      value.set(to);
      return;
    }
    const controls = animate(value, to, { duration: 0.7, ease: [0.22, 1, 0.36, 1], delay: 0.2 });
    return () => controls.stop();
  }, [reduce, to, value]);

  return (
    <div className="mt-3 space-y-1.5" data-testid="mastery-meter">
      <p className="sr-only">
        Your mastery of {concept} went from {from}% to {to}%.
      </p>
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 text-xs text-muted" aria-hidden>
        <span>Your mastery of {concept}</span>
        <span className="flex flex-none items-center gap-2">
          <span className="tabular-nums text-subtle">{from}% →</span>
          <motion.span className="text-sm font-semibold tabular-nums text-fg">{shown}</motion.span>
          {points !== 0 && (
            <span
              className={cn(
                "rounded-full px-1.5 py-px text-[11px] font-medium tabular-nums",
                points > 0 ? "bg-success-soft text-success ring-1 ring-success/30" : "bg-surface text-muted ring-1 ring-line"
              )}
            >
              {signedPoints(points)}
            </span>
          )}
        </span>
      </div>
      <div className="relative h-2 rounded-full bg-surface ring-1 ring-line" aria-hidden>
        <span className="absolute inset-y-0 left-0 rounded-full bg-primary/25" style={{ width: `${Math.min(from, to)}%` }} />
        <motion.span
          className="absolute inset-y-0 left-0 rounded-full bg-primary"
          initial={{ width: `${reduce ? to : from}%` }}
          animate={{ width: `${to}%` }}
          transition={{ duration: reduce ? 0 : 0.7, ease: [0.22, 1, 0.36, 1], delay: 0.2 }}
        />
        {TICKS.map((t) => (
          <span key={t.at} title={`${t.label} (${Math.round(t.at * 100)}%)`} className="absolute -inset-y-0.5 w-px bg-line-strong" style={{ left: `${t.at * 100}%` }} />
        ))}
      </div>
    </div>
  );
}
