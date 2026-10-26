"use client";

import { motion } from "motion/react";
import React from "react";
import { SessionAnswer } from "@/lib/moments";
import { cn } from "../ui/cn";

/** This session so far: one mark per answer (✓ right, ✕ not yet) and a ring for the current step. */
export function SessionStrip({ answers, current, names }: { answers: SessionAnswer[]; current: boolean; names: Record<string, string> }) {
  const recent = answers.slice(-12);
  const right = answers.filter((a) => a.correct).length;
  return (
    <div className="flex items-center gap-3" data-testid="session-strip">
      <ol className="flex items-center gap-1.5" aria-label={`This session: ${answers.length} answered, ${right} right`}>
        {recent.map((a, i) => (
          <motion.li
            key={answers.length - recent.length + i}
            initial={{ scale: 0.4, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className={cn(
              "flex h-4 w-4 items-center justify-center rounded-full text-[9px] font-bold",
              a.correct ? "bg-success text-white" : "bg-surface-2 text-muted ring-1 ring-line-strong"
            )}
            title={`${names[a.conceptId] ?? a.conceptId}: ${a.correct ? "right" : "not yet"}`}
          >
            <span aria-hidden>{a.correct ? "✓" : "✕"}</span>
            <span className="sr-only">{a.correct ? "right" : "not yet"}</span>
          </motion.li>
        ))}
        {current && (
          <li className="h-4 w-4 rounded-full ring-2 ring-primary/50 ring-offset-2 ring-offset-bg" aria-label="current question">
            <span className="sr-only">current question</span>
          </li>
        )}
      </ol>
    </div>
  );
}
