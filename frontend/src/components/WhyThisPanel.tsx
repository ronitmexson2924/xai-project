"use client";

import { AnimatePresence, motion } from "motion/react";
import React, { useMemo, useState } from "react";
import { api, ApiException, RecommendationWhy } from "@/lib/api";
import type { TelemetryEventType } from "@/lib/useExplanationTelemetry";
import { Button } from "./ui/Button";
import { ease } from "./ui/motion";

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
    <div className="rounded-xl border border-line bg-surface-2/60" data-testid="why-panel">
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left text-sm font-medium text-fg"
      >
        <span className="inline-flex items-center gap-2">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="text-primary" aria-hidden>
            <circle cx="12" cy="12" r="9" />
            <path d="M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6V14M12 17h.01" />
          </svg>
          Why this?
        </span>
        <motion.span animate={{ rotate: open ? 180 : 0 }} transition={{ duration: 0.2 }} className="text-subtle" aria-hidden>
          ▾
        </motion.span>
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease }}
            className="overflow-hidden"
          >
            <div className="space-y-4 border-t border-line px-4 py-4 text-sm leading-relaxed text-muted">
              {!why && !error && (
                <div className="space-y-2" aria-busy>
                  <div className="h-3 w-3/4 animate-pulse rounded bg-line" />
                  <div className="h-3 w-1/2 animate-pulse rounded bg-line" />
                </div>
              )}
              {error && <p className="text-danger">{error}</p>}

              {why && (
                <>
                  <section className="space-y-1">
                    <h4 className="text-xs font-semibold uppercase tracking-wide text-subtle">Why this step now</h4>
                    <p data-testid="why-summary" className="text-fg">
                      {why.rationale.summary}
                    </p>
                    {why.rationale.alternative && <p>Otherwise we would have chosen: {why.rationale.alternative}</p>}
                  </section>

                  {why.rationale.counterfactuals.length > 0 && (
                    <section className="space-y-1">
                      <h4 className="text-xs font-semibold uppercase tracking-wide text-subtle">What would change it</h4>
                      <ul className="space-y-2">
                        {why.rationale.counterfactuals.map((cf, i) => (
                          <li key={i} className="rounded-lg border border-line bg-surface px-3 py-2">
                            <span className="text-fg">{cf.condition}</span>
                            <span className="mx-1.5 text-subtle" aria-label="then">
                              →
                            </span>
                            {cf.outcome}.
                          </li>
                        ))}
                      </ul>
                    </section>
                  )}

                  {why.style && (
                    <section className="space-y-1">
                      <h4 className="text-xs font-semibold uppercase tracking-wide text-subtle">Why the explanation reads like this</h4>
                      <p>{why.style.summary}</p>
                      <p className="text-xs text-subtle">
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
                          <span>Did this make sense?</span>
                          <Button size="sm" variant="secondary" onClick={() => rate(true)}>
                            Yes
                          </Button>
                          <Button size="sm" variant="secondary" onClick={() => rate(false)}>
                            No
                          </Button>
                        </>
                      ) : (
                        <span className="text-success">Thanks for the feedback.</span>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
