"use client";

import React, { useEffect, useState } from "react";
import { api, ApiException, BeliefExplanation } from "@/lib/api";
import { Badge } from "./ui/Badge";
import { Progress } from "./ui/Progress";

const CONFIDENCE = { tentative: "warning", moderate: "accent", confident: "success" } as const;

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

  if (error) return <p className="text-sm text-danger">{error}</p>;
  if (!belief)
    return (
      <div className="space-y-2" aria-busy>
        <div className="h-4 w-1/2 animate-pulse rounded bg-surface-2" />
        <div className="h-3 w-full animate-pulse rounded bg-surface-2" />
        <div className="h-3 w-4/5 animate-pulse rounded bg-surface-2" />
      </div>
    );
  return (
    <div className="space-y-3" data-testid={`belief-${subject}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-semibold text-fg">{belief.label}</span>
        <Badge tone={CONFIDENCE[belief.confidence as keyof typeof CONFIDENCE] ?? "neutral"}>{belief.confidence}</Badge>
      </div>
      {showValue && <Progress value={belief.value} label={`${belief.label} estimate`} />}
      <p className="text-sm leading-relaxed text-muted">{belief.summary}</p>
      {belief.top_evidence.length > 0 && (
        <details className="group text-sm">
          <summary className="cursor-pointer list-none text-accent hover:text-accent-hover">
            <span className="inline-flex items-center gap-1">
              What this is based on
              <span aria-hidden className="transition-transform group-open:rotate-90">›</span>
            </span>
          </summary>
          <ul className="mt-2 space-y-1.5 border-l border-line pl-3 text-muted">
            {belief.top_evidence.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
