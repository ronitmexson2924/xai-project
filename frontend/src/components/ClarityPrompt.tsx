"use client";

import { AnimatePresence, motion } from "motion/react";
import React, { useMemo, useState } from "react";
import { ease } from "./ui/motion";

interface ClarityPromptProps {
  explanationId: string;
  onRate: (rating: number) => void;
  forceShow?: boolean;
}

const RATINGS = [
  { value: 1, label: "Confusing" },
  { value: 2, label: "A bit dense" },
  { value: 3, label: "OK" },
  { value: 4, label: "Clear" },
  { value: 5, label: "Very clear" },
];

/** The 1-tap clarity rating, asked for about one explanation in three. */
export function ClarityPrompt({ explanationId, onRate, forceShow = false }: ClarityPromptProps) {
  const [rated, setRated] = useState<number | null>(null);
  const [dismissed, setDismissed] = useState(false);

  // Deterministic 1 in 3 prompt selection based on explanationId string hash
  const shouldShow = useMemo(() => {
    if (forceShow) return true;
    let hash = 0;
    for (let i = 0; i < explanationId.length; i++) {
      hash = (hash << 5) - hash + explanationId.charCodeAt(i);
      hash |= 0;
    }
    return Math.abs(hash) % 3 === 0;
  }, [explanationId, forceShow]);

  const handleRating = (rating: number) => {
    setRated(rating);
    onRate(rating);
    setTimeout(() => setDismissed(true), 2500);
  };

  return (
    <AnimatePresence>
      {shouldShow && !dismissed && (
        <motion.div
          exit={{ opacity: 0, height: 0, marginTop: 0 }}
          transition={{ duration: 0.3, ease }}
          className="overflow-hidden rounded-xl border border-line bg-surface-2 p-3.5"
        >
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm text-fg">How clear was this explanation?</p>
            <button
              type="button"
              onClick={() => setDismissed(true)}
              className="rounded-md px-1.5 text-sm text-subtle hover:text-fg"
              aria-label="Skip clarity rating"
            >
              ✕
            </button>
          </div>
          {rated !== null ? (
            <p className="mt-2 text-sm text-success">Thanks. This helps tune how explanations are written for you.</p>
          ) : (
            <div className="mt-3 grid grid-cols-5 gap-1.5" role="group" aria-label="Clarity rating">
              {RATINGS.map((r) => (
                <button
                  key={r.value}
                  type="button"
                  onClick={() => handleRating(r.value)}
                  className="rounded-lg border border-line bg-surface px-1 py-1.5 text-xs text-muted transition-all hover:border-accent/50 hover:text-fg active:scale-95"
                >
                  {r.label}
                </button>
              ))}
            </div>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
