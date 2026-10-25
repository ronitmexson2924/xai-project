"use client";

import React, { useEffect, useState } from "react";
import { api, BeliefExplanation as Belief } from "@/lib/api";

const CONFIDENCE_STYLE: Record<string, string> = {
  low: "bg-amber-500/10 text-amber-300 border-amber-500/30",
  medium: "bg-sky-500/10 text-sky-300 border-sky-500/30",
  high: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30",
};

/** "Why we think this" (XAI E4): the system's belief about a concept or trait, how sure it is,
 * and the events that moved it most. */
export function BeliefExplanation({ subject }: { subject: string }) {
  const [belief, setBelief] = useState<Belief | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let live = true;
    api.learners
      .explain(subject)
      .then((b) => live && setBelief(b))
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
    };
  }, [subject]);

  if (failed) return <p className="text-xs text-slate-500">No explanation available yet.</p>;
  if (!belief) return <p className="text-xs text-slate-500">Loading…</p>;
  return (
    <div className="space-y-2 rounded-xl border border-slate-800 bg-slate-950/60 p-4 text-sm">
      <div className="flex items-center justify-between gap-2">
        <span className="font-semibold text-slate-100">Why we think this</span>
        <span
          className={`rounded-full border px-2 py-0.5 text-[11px] ${
            CONFIDENCE_STYLE[belief.confidence] ?? CONFIDENCE_STYLE.low
          }`}
        >
          {belief.confidence} confidence
        </span>
      </div>
      <p className="text-slate-300">{belief.summary}</p>
      {belief.top_evidence && belief.top_evidence.length > 0 && (
        <ul className="list-disc space-y-0.5 pl-5 text-xs text-slate-400">
          {belief.top_evidence.map((e, i) => (
            <li key={i}>{e}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
