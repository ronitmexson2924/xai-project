"use client";

import { motion } from "motion/react";
import React from "react";
import { cn } from "./cn";

/** Animated progress bar; value in [0, 1]. */
export function Progress({ value, label, className, tone = "accent" }: { value: number; label: string; className?: string; tone?: "accent" | "success" }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={pct}
      className={cn("h-1.5 w-full overflow-hidden rounded-full bg-surface-2", className)}
    >
      <motion.div
        className={cn("h-full rounded-full", tone === "success" ? "bg-success" : "bg-accent")}
        initial={false}
        animate={{ width: `${pct}%` }}
        transition={{ type: "spring", stiffness: 120, damping: 24 }}
      />
    </div>
  );
}
