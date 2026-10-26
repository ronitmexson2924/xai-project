"use client";

import { motion, useReducedMotion } from "motion/react";
import React from "react";
import { ENGAGEMENT_UI } from "@/lib/engagement";
import { Moment } from "@/lib/moments";
import { cn } from "../ui/cn";

/**
 * The line after an answer. With ENGAGEMENT_UI off it is the plain "Correct." / "Not quite." card;
 * with it on, a warmer moment (`moment`), including "you beat the prediction" in apricot.
 * Never red for a wrong answer: a wrong answer is part of learning, not an error.
 */
export function ResultMoment({
  correct,
  correctAnswer,
  moment,
  children,
}: {
  correct: boolean;
  correctAnswer?: string | null;
  moment: Moment | null;
  children?: React.ReactNode;
}) {
  const reduce = useReducedMotion();
  const warm = ENGAGEMENT_UI && moment !== null;
  const beat = warm && moment.kind === "beat";
  const title = warm ? moment.title : correct ? "Correct." : "Not quite.";

  return (
    <motion.div
      data-testid="attempt-result"
      data-moment={warm ? moment.kind : undefined}
      initial={{ opacity: 0, scale: 0.97 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ type: "spring", stiffness: 400, damping: 28 }}
      className={cn(
        "rounded-xl border p-5",
        beat ? "border-accent bg-accent-soft" : correct ? "border-success/40 bg-success-soft" : "border-line-strong bg-surface-2"
      )}
    >
      <div className="flex items-start gap-3">
        <span className="relative flex-none">
          <motion.span
            initial={warm && correct ? { scale: 0.4 } : false}
            animate={{ scale: 1 }}
            transition={{ type: "spring", stiffness: 500, damping: 18 }}
            className={cn(
              "flex h-7 w-7 items-center justify-center rounded-full",
              beat ? "bg-accent text-accent-fg" : correct ? "bg-success text-white" : "bg-surface text-muted ring-1 ring-line-strong"
            )}
            aria-hidden
          >
            {correct ? (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                <motion.path
                  d="M5 12.5 10 17.5 19 7"
                  initial={warm && !reduce ? { pathLength: 0 } : false}
                  animate={{ pathLength: 1 }}
                  transition={{ duration: 0.35, delay: 0.1, ease: "easeOut" }}
                />
              </svg>
            ) : (
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round">
                <path d="M6 6l12 12M18 6 6 18" />
              </svg>
            )}
          </motion.span>
          {beat && !reduce && <Sparkle />}
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="font-semibold text-fg">{title}</h2>
          {warm && moment.detail && <p className="mt-0.5 text-sm text-muted">{moment.detail}</p>}
          {!correct && correctAnswer && (
            <p className="mt-0.5 text-sm text-muted">
              The expected answer: <span className="font-medium text-fg">{correctAnswer}</span>
            </p>
          )}
          {children}
        </div>
      </div>
    </motion.div>
  );
}

/** A one-time burst of six small apricot stars around the tick. Hand-drawn, no library. */
function Sparkle() {
  const rays = [0, 60, 120, 180, 240, 300];
  return (
    <span className="pointer-events-none absolute inset-0" aria-hidden>
      {rays.map((deg, i) => {
        const rad = (deg * Math.PI) / 180;
        return (
          <motion.svg
            key={deg}
            width="8"
            height="8"
            viewBox="0 0 10 10"
            className="absolute left-1/2 top-1/2 -ml-1 -mt-1 text-accent"
            initial={{ x: 0, y: 0, scale: 0, opacity: 1 }}
            animate={{ x: Math.cos(rad) * 22, y: Math.sin(rad) * 22, scale: [0, 1.1, 0.6], opacity: [1, 1, 0] }}
            transition={{ duration: 0.8, delay: 0.15 + i * 0.02, ease: "easeOut" }}
          >
            <path d="M5 0 6.2 3.8 10 5 6.2 6.2 5 10 3.8 6.2 0 5 3.8 3.8Z" fill="currentColor" />
          </motion.svg>
        );
      })}
    </span>
  );
}
