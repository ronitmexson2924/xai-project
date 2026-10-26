"use client";

import { AnimatePresence, motion } from "motion/react";
import React from "react";
import type { ChangeNotice as ChangeNoticeData } from "@/lib/api";
import { ease } from "./ui/motion";

/** XAI E5: what the learner's answer or feedback just changed, in their own words. */
export function ChangeNotice({ notice }: { notice: ChangeNoticeData | null | undefined }) {
  const show = Boolean(notice && notice.messages.length > 0);
  return (
    <div role="status" aria-live="polite">
      <AnimatePresence>
        {show && (
          <motion.div
            data-testid="change-notice"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.35, ease }}
            className="flex gap-3 rounded-xl border border-primary/25 bg-primary-soft p-4 text-sm"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mt-0.5 flex-none text-primary" aria-hidden>
              <path d="M3 12h4l3 8 4-16 3 8h4" />
            </svg>
            <div className="space-y-1">
              <p className="font-medium text-fg">What this changed</p>
              <ul className="space-y-0.5 text-muted">
                {notice!.messages.map((m, i) => (
                  <li key={i}>{m}</li>
                ))}
              </ul>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
