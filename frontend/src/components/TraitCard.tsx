"use client";

import React from "react";
import type { LearnerState } from "@/lib/api";
import { BeliefPanel } from "./BeliefPanel";

/**
 * The learner's trait estimates, each with the system's own explanation of where it came from
 * (XAI E4). The wording comes from the learner model, so it says what was observed and what the
 * app does with it, never a label for the learner.
 */
export default function TraitCard({ traits }: { traits: LearnerState["traits"] }) {
  if (!traits?.traits) return null;
  return (
    <div className="rounded-3xl border border-white/10 bg-slate-900/60 p-6 sm:p-8 shadow-xl" data-testid="trait-card">
      <div className="mb-6 border-b border-white/5 pb-4">
        <h2 className="text-lg sm:text-xl font-bold text-white">How explanations are adapted to you</h2>
        <p className="text-xs text-slate-400 mt-1">
          Each estimate shows how sure we are and what it is based on. They change as you give feedback.
        </p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {Object.keys(traits.traits).map((trait) => (
          <div key={trait} className="rounded-2xl border border-slate-800 bg-slate-950/60 p-5">
            <BeliefPanel subject={trait} />
          </div>
        ))}
      </div>
    </div>
  );
}
