"use client";

import React from "react";
import type { LearnerState } from "@/lib/api";
import { BeliefPanel } from "./BeliefPanel";
import { Card, SectionTitle } from "./ui/Card";

/**
 * Trait estimates, each with the learner model's own explanation of where it came from (XAI E4).
 * The wording comes from the model: what was observed and what the app does with it, never a label.
 */
export default function TraitCard({ traits }: { traits: LearnerState["traits"] }) {
  if (!traits?.traits) return null;
  return (
    <section className="space-y-4" data-testid="trait-card">
      <SectionTitle title="How explanations adapt to you" hint="Each estimate shows how sure we are and what it is based on." />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Object.keys(traits.traits).map((trait) => (
          <Card key={trait} className="p-5">
            <BeliefPanel subject={trait} />
          </Card>
        ))}
      </div>
    </section>
  );
}
