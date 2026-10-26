"use client";

import { AnimatePresence, motion } from "motion/react";
import React, { useRef, useState } from "react";
import type { Concept, Explanation } from "@/lib/api";
import { useExplanationTelemetry } from "@/lib/useExplanationTelemetry";
import { ClarityPrompt } from "./ClarityPrompt";
import { Markdown } from "./Markdown";
import { WhyThisPanel } from "./WhyThisPanel";
import { Badge } from "./ui/Badge";
import { Button } from "./ui/Button";
import { ease } from "./ui/motion";

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
  const tags = [
    style.example_first ? "Example first" : "Rule first",
    style.length === "short" ? "Short" : style.length === "long" ? "In depth" : "Medium length",
    style.depth === "why" ? "Why it works" : "How it works",
  ];
  return (
    <motion.div
      ref={ref}
      data-testid="explanation-card"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease }}
      className="space-y-5 rounded-xl border border-line bg-surface p-5 shadow-card sm:p-7"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-primary">Explanation</p>
          <h2 className="mt-1 text-lg font-semibold tracking-tight text-fg">
            {concept?.name ?? explanation.concept_ids.join(", ")}
          </h2>
        </div>
        <div className="flex flex-wrap gap-1.5" aria-label="How this explanation is written">
          {tags.map((t) => (
            <Badge key={t}>{t}</Badge>
          ))}
        </div>
      </div>

      <div ref={bodyRef} className="scroll-mt-24 text-[15px] leading-7 text-fg">
        <Markdown text={explanation.body_markdown} />
      </div>

      <AnimatePresence initial={false}>
        {expanded && concept && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease }}
            className="overflow-hidden"
          >
            <div className="space-y-3 rounded-xl border border-line bg-surface-2/60 p-4 text-sm text-muted">
              <p className="text-xs font-semibold uppercase tracking-wide text-subtle">Worked example</p>
              <Markdown text={"```python\n" + concept.card.worked_example + "\n```"} />
              <p className="text-xs font-semibold uppercase tracking-wide text-subtle">Common pitfall</p>
              <Markdown text={concept.card.pitfall} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          {concept && (
            <Button size="sm" variant="secondary" onClick={toggleExpand} aria-expanded={expanded}>
              {expanded ? "Hide worked example" : "Show worked example"}
            </Button>
          )}
          <Button size="sm" variant="ghost" onClick={readAgain}>
            Read again
          </Button>
        </div>
        {onDismiss && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              trackDismissed();
              onDismiss();
            }}
          >
            Dismiss
          </Button>
        )}
      </div>

      <ClarityPrompt explanationId={explanation.id} onRate={trackClarityRated} />
      <WhyThisPanel recommendationId={explanation.recommendation_id} recordEvent={recordEvent} />
    </motion.div>
  );
}
