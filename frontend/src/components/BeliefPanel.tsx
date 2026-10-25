"use client";

import React, { useEffect, useState } from "react";
import { api, ApiException, BeliefExplanation } from "@/lib/api";

const CONFIDENCE_STYLE: Record<string, string> = {
  tentative: "text-amber-300 bg-amber-500/10 border-amber-500/20",
  moderate: "text-indigo-300 bg-indigo-500/10 border-indigo-500/20",
  confident: "text-emerald-300 bg-emerald-500/10 border-emerald-500/20",
};

/** XAI E4: "Why do you think that about me?" for one concept or trait, from the audit log. */
export function BeliefPanel({ subject, showValue = true }: { subject: string; showValue?: boolean }) {
  const [belief, setBelief] = useState<BeliefExplanation | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api.xai
      .belief(subject)
      .then((b) => alive && setBelief(b))
      .catch((err) => alive && setError(err instanceof ApiException ? err.message : "Could not load."));
    return () => {
      alive = false;
    };
  }, [subject]);

  if (error) return <p className="text-xs text-rose-300">{error}</p>;
  if (!belief) return <p className="text-xs text-slate-500">Loading…</p>;
  return (
    <div className="space-y-2" data-testid={`belief-${subject}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-semibold text-white">{belief.label}</span>
        <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${CONFIDENCE_STYLE[belief.confidence] ?? ""}`}>
          {belief.confidence}
        </span>
      </div>
      {showValue && (
        <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden" aria-hidden>
          <div className="h-full bg-indigo-500" style={{ width: `${Math.round(belief.value * 100)}%` }} />
        </div>
      )}
      <p className="text-xs text-slate-300 leading-relaxed">{belief.summary}</p>
      {belief.top_evidence.length > 0 && (
        <details className="text-xs text-slate-400">
          <summary className="cursor-pointer text-indigo-400">What this is based on</summary>
          <ul className="list-disc pl-5 mt-1 space-y-0.5">
            {belief.top_evidence.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
