"use client";

import React, { useMemo, useState } from "react";

interface ClarityPromptProps {
  explanationId: string;
  onRate: (rating: number) => void;
  forceShow?: boolean;
}

export function ClarityPrompt({
  explanationId,
  onRate,
  forceShow = false,
}: ClarityPromptProps) {
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

  if (!shouldShow || dismissed) {
    return null;
  }

  const handleRating = (rating: number) => {
    setRated(rating);
    onRate(rating);
    setTimeout(() => {
      setDismissed(true);
    }, 2500);
  };

  const ratings = [
    { value: 1, label: "Confusing", emoji: "😕" },
    { value: 2, label: "A bit dense", emoji: "🤔" },
    { value: 3, label: "Adequate", emoji: "👌" },
    { value: 4, label: "Clear", emoji: "💡" },
    { value: 5, label: "Crystal clear", emoji: "✨" },
  ];

  return (
    <div className="rounded-xl border border-indigo-500/30 bg-indigo-950/40 p-3.5 backdrop-blur-sm transition-all duration-300">
      <div className="flex items-center justify-between gap-3">
        <div className="space-y-0.5">
          <span className="text-xs font-semibold text-indigo-300 flex items-center gap-1.5">
            <span>Quick Check</span>
            <span className="text-[10px] px-1.5 py-0.2 rounded bg-indigo-500/20 text-indigo-400">
              1-tap
            </span>
          </span>
          <p className="text-xs text-slate-300">
            How clear was this explanation for you?
          </p>
        </div>

        <button
          type="button"
          onClick={() => setDismissed(true)}
          className="text-slate-500 hover:text-slate-400 text-xs px-1.5 py-0.5"
          aria-label="Skip clarity rating"
        >
          ✕
        </button>
      </div>

      {rated !== null ? (
        <div className="mt-2.5 text-xs text-emerald-400 font-medium flex items-center gap-1.5">
          <span>✓ Thanks! Your rating helps calibrate future explanation styles.</span>
        </div>
      ) : (
        <div className="mt-3 flex items-center justify-between gap-1.5 sm:gap-2">
          {ratings.map((r) => (
            <button
              key={r.value}
              type="button"
              onClick={() => handleRating(r.value)}
              className="flex-1 flex flex-col sm:flex-row items-center justify-center gap-1 py-1.5 px-2 rounded-lg bg-slate-900/80 border border-slate-700/60 hover:border-indigo-400/60 hover:bg-indigo-900/40 text-xs text-slate-200 transition-all active:scale-95"
            >
              <span className="text-sm">{r.emoji}</span>
              <span className="text-[11px] hidden md:inline">{r.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
