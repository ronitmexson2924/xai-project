"use client";

import React, { useState } from "react";
import { api, RecommendationWhy } from "@/lib/api";
import { Telemetry } from "@/lib/useExplanationTelemetry";

interface WhyPanelProps {
  recommendationId: string;
  telemetry: Telemetry;
}

/** "Why this?" (XAI E1-E3, docs/XAI_DESIGN.md): the stored rationale, what would change the
 * decision, and why this style. A 1-tap "Did this make sense?" appears on about 1 in 5. */
export function WhyPanel({ recommendationId, telemetry }: WhyPanelProps) {
  const [open, setOpen] = useState(false);
  const [why, setWhy] = useState<RecommendationWhy | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rated, setRated] = useState<boolean | null>(null);
  const askRating = hash(recommendationId) % 5 === 0;

  const toggle = async () => {
    const next = !open;
    setOpen(next);
    if (!next) return;
    telemetry.recordEvent("why_opened");
    if (why) return;
    try {
      setWhy(await api.recommendations.why(recommendationId));
    } catch {
      setError("The reasons for this step could not be loaded.");
    }
  };

  const rate = (helpful: boolean) => {
    setRated(helpful);
    telemetry.recordEvent("why_rated", { helpful });
  };

  return (
    <div className="rounded-2xl border border-indigo-500/20 bg-indigo-950/20 p-4">
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        className="flex w-full items-center justify-between text-left text-sm font-semibold text-indigo-200"
      >
        <span>Why this?</span>
        <span aria-hidden>{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="mt-3 space-y-3 text-sm text-slate-200">
          {error && <p className="text-rose-300">{error}</p>}
          {!why && !error && <p className="text-slate-400">Loading…</p>}
          {why && (
            <>
              <p>{why.rationale.summary}</p>
              {why.rationale.counterfactuals && why.rationale.counterfactuals.length > 0 && (
                <ul className="list-disc space-y-1 pl-5 text-slate-300">
                  {why.rationale.counterfactuals.map((cf, i) => (
                    <li key={i}>
                      {cf.condition}: {cf.outcome}.
                    </li>
                  ))}
                </ul>
              )}
              {why.style && (
                <p className="text-xs text-slate-400">
                  <strong className="text-slate-300">Why this style:</strong> {why.style.summary}
                </p>
              )}
              {askRating && rated === null && (
                <div className="flex items-center gap-2 pt-1 text-xs">
                  <span className="text-slate-400">Did this make sense?</span>
                  <button type="button" onClick={() => rate(true)}
                    className="rounded-md border border-emerald-500/30 px-2 py-0.5 text-emerald-300 hover:bg-emerald-500/10">
                    Yes
                  </button>
                  <button type="button" onClick={() => rate(false)}
                    className="rounded-md border border-rose-500/30 px-2 py-0.5 text-rose-300 hover:bg-rose-500/10">
                    No
                  </button>
                </div>
              )}
              {rated !== null && <p className="text-xs text-slate-500">Thanks for the feedback.</p>}
            </>
          )}
        </div>
      )}
    </div>
  );
}

function hash(text: string): number {
  let h = 0;
  for (let i = 0; i < text.length; i++) {
    h = (h << 5) - h + text.charCodeAt(i);
    h |= 0;
  }
  return Math.abs(h);
}
