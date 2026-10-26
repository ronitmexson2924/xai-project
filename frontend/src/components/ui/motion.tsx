"use client";

import { motion, MotionConfig, type Variants } from "motion/react";
import React from "react";

/** Wrap the app: every animation honours the user's reduced-motion setting. */
export function MotionProvider({ children }: { children: React.ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}

export const ease = [0.22, 1, 0.36, 1] as const;

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5, ease } },
};

export const stagger = (gap = 0.06, delay = 0): Variants => ({
  hidden: {},
  show: { transition: { staggerChildren: gap, delayChildren: delay } },
});

/** Children that use `variants={fadeUp}` appear one after another. */
export function Stagger({ children, className, gap, delay, as = "div" }: { children: React.ReactNode; className?: string; gap?: number; delay?: number; as?: "div" | "ul" | "section" }) {
  const Tag = motion[as];
  return (
    <Tag className={className} variants={stagger(gap, delay)} initial="hidden" animate="show">
      {children}
    </Tag>
  );
}

export function FadeUp({ children, className, delay = 0 }: { children: React.ReactNode; className?: string; delay?: number }) {
  return (
    <motion.div className={className} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease, delay }}>
      {children}
    </motion.div>
  );
}

export const Item = motion.div;
