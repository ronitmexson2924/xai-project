"use client";

import React, { useMemo, useState } from "react";
import { api, ApiException, RecommendationWhy } from "@/lib/api";
import type { TelemetryEventType } from "@/lib/useExplanationTelemetry";

interface WhyThisPanelProps {
  recommendationId: string;
  /** records why_opened / why_rated on the explanation shown with this recommendation */
  recordEvent?: (type: TelemetryEventType, payload?: Record<string, string | number | boolean | null>) => void;
}

const CONFIDENCE_LABEL: Record<string, string> = {
  tentative: "We're not sure yet",
  moderate: "Fairly sure",
  confident: "Confident",
};

/**
 * XAI E1-E3 ("Why this?"): the reasoning stored when the planner made this recommendation, what
 * would change it (verified counterfactuals), and why the explanation is written this way. All
 * text comes from the server's rationale; nothing here is invented by the UI.
 */
export function WhyThisPanel({ recommendationId, recordEvent }: WhyThisPanelProps) {
  const [open, setOpen] = useState(false);
  const [why, setWhy] = useState<RecommendationWhy | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rated, setRated] = useState<boolean | null>(null);

  // the 1-tap "Did this make sense?" is asked for about 1 in 5 recommendations (XAI_DESIGN §5)
  const askRating = useMemo(() => {
    let h = 0;
    for (let i = 0; i < recommendationId.length; i++) h = (h * 31 + recommendationId.charCodeAt(i)) | 0;
    return Math.abs(h) % 5 === 0;
  }, [recommendationId]);

  const toggle = async () => {
    const next = !open;
    setOpen(next);
    if (!next || why) return;
    recordEvent?.("why_opened");
    try {
      setWhy(await api.xai.why(recommendationId));
    } catch (err) {
      setError(err instanceof ApiException ? err.message : "Could not load the reasoning.");
    }
  };

  const rate = (helpful: boolean) => {
    setRated(helpful);
    recordEvent?.("why_rated", { helpful });
  };

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4 sm:p-5 space-y-3" data-testid="why-panel">
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        className="w-full flex items-center justify-between text-sm font-semibold text-white"
      >
        <span>Why this?</span>
        <span className="text-xs text-indigo-400">{open ? "Hide ▲" : "Show the reasoning ▼"}</span>
      </button>

      {open && !why && !error && <p className="text-xs text-slate-400">Loading…</p>}
      {open && error && <p className="text-xs text-rose-300">{error}</p>}

      {open && why && (
        <div className="space-y-4 text-xs text-slate-300 leading-relaxed">
          <section className="space-y-1">
            <h4 className="font-semibold text-slate-100">Why this question now</h4>
            <p data-testid="why-summary">{why.rationale.summary}</p>
            {why.rationale.alternative && (
              <p className="text-slate-400">Otherwise we would have chosen: {why.rationale.alternative}</p>
            )}
          </section>

          {why.rationale.counterfactuals.length > 0 && (
            <section className="space-y-1">
              <h4 className="font-semibold text-slate-100">What would change it</h4>
              <ul className="list-disc pl-5 space-y-1">
                {why.rationale.counterfactuals.map((cf, i) => (
                  <li key={i}>
                    If you {cf.condition}, {cf.outcome}.
                  </li>
                ))}
              </ul>
            </section>
          )}

          {why.style && (
            <section className="space-y-1">
              <h4 className="font-semibold text-slate-100">Why the explanation looks like this</h4>
              <p>{why.style.summary}</p>
              <p className="text-slate-500">
                {CONFIDENCE_LABEL[why.style.confidence] ?? why.style.confidence}
                {why.style.p_best != null &&
                  ` · chance this style suits you best: ${Math.round(why.style.p_best * 100)}%`}
              </p>
            </section>
          )}

          {askRating && (
            <div className="flex items-center gap-2 pt-1">
              {rated === null ? (
                <>
                  <span className="text-slate-400">Did this make sense?</span>
                  <button type="button" onClick={() => rate(true)} className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700">
                    Yes
                  </button>
                  <button type="button" onClick={() => rate(false)} className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700">
                    No
                  </button>
                </>
              ) : (
                <span className="text-emerald-400">Thanks for the feedback.</span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
