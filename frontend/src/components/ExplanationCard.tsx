"use client";

import React, { useRef, useState } from "react";
import type { Concept, Explanation } from "@/lib/api";
import { useExplanationTelemetry } from "@/lib/useExplanationTelemetry";
import { ClarityPrompt } from "./ClarityPrompt";
import { Markdown } from "./Markdown";
import { WhyThisPanel } from "./WhyThisPanel";

interface ExplanationCardProps {
  explanation: Explanation;
  concept?: Concept;
  onDismiss?: () => void;
}

/**
 * The grounded explanation (Module B) with its telemetry (Module C) and the "Why this?" panel.
 * The optional deep dive shows the concept card's own worked example and pitfall, so everything on
 * the card comes from reviewed content (decision D6).
 */
export function ExplanationCard({ explanation, concept, onDismiss }: ExplanationCardProps) {
  const [expanded, setExpanded] = useState(false);
  const bodyRef = useRef<HTMLDivElement | null>(null);
  const { ref, recordEvent, trackExpanded, trackCollapsed, trackReplayed, trackClarityRated, trackDismissed } =
    useExplanationTelemetry(explanation.id);

  const toggleExpand = () => {
    setExpanded(!expanded);
    if (expanded) trackCollapsed();
    else trackExpanded();
  };

  const readAgain = () => {
    trackReplayed();
    bodyRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const style = explanation.style;
  return (
    <div
      ref={ref}
      data-testid="explanation-card"
      className="rounded-2xl border border-slate-800 bg-slate-900/90 p-5 sm:p-6 shadow-xl space-y-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-800/80">
        <h3 className="text-sm font-semibold text-white">
          {concept?.name ?? explanation.concept_ids.join(", ")}
        </h3>
        <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
          <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
            {style.example_first ? "example first" : "rule first"}
          </span>
          <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
            {style.length}
          </span>
          <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
            {style.depth === "why" ? "why it works" : "how it works"}
          </span>
        </div>
      </div>

      <div ref={bodyRef} className="text-sm text-slate-200 leading-relaxed">
        <Markdown text={explanation.body_markdown} />
      </div>

      {expanded && concept && (
        <div className="p-4 rounded-xl bg-slate-950/70 border border-indigo-500/20 space-y-3 text-xs text-slate-300">
          <div className="font-semibold text-indigo-300">Worked example</div>
          <Markdown text={"```python\n" + concept.card.worked_example + "\n```"} />
          <div className="font-semibold text-indigo-300">Common pitfall</div>
          <Markdown text={concept.card.pitfall} />
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          {concept && (
            <button
              type="button"
              onClick={toggleExpand}
              aria-expanded={expanded}
              className="text-xs font-medium px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700"
            >
              {expanded ? "Hide worked example ▲" : "Show worked example ▼"}
            </button>
          )}
          <button
            type="button"
            onClick={readAgain}
            className="text-xs font-medium px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700"
          >
            Read again
          </button>
        </div>
        {onDismiss && (
          <button
            type="button"
            onClick={() => {
              trackDismissed();
              onDismiss();
            }}
            className="text-xs text-slate-400 hover:text-white px-2 py-1"
          >
            Dismiss
          </button>
        )}
      </div>

      <ClarityPrompt explanationId={explanation.id} onRate={trackClarityRated} />
      <WhyThisPanel recommendationId={explanation.recommendation_id} recordEvent={recordEvent} />
    </div>
  );
}
