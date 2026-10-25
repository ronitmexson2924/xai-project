"use client";

import React, { useState } from "react";
import { ReasonEvidence } from "@/lib/api";

interface ReasonsPanelProps {
  reasons: ReasonEvidence[];
  targetConceptId?: string;
}

export function ReasonsPanel({ reasons, targetConceptId }: ReasonsPanelProps) {
  const [showTechnical, setShowTechnical] = useState(false);

  if (!reasons || reasons.length === 0) {
    return null;
  }

  const formatReason = (r: ReasonEvidence) => {
    const concept = r.concept_id || targetConceptId || "this concept";
    const valPercent = r.value !== null && r.value !== undefined ? Math.round(r.value * 100) : null;

    switch (r.code) {
      case "PREREQ_GAP":
        return {
          title: "Prerequisite Gap",
          color: "border-amber-500/30 bg-amber-500/10 text-amber-300",
          icon: "⚡",
          summary: `Strengthening foundational prerequisite: ${concept}${
            valPercent !== null ? ` (current mastery: ${valPercent}%)` : ""
          }.`,
          detail: "Your mastery estimate indicated that reviewing this prerequisite will prevent confusion later on.",
        };
      case "READY_FOR_NEXT":
        return {
          title: "Ready to Advance",
          color: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
          icon: "🚀",
          summary: `You demonstrated strong mastery on prerequisites and are ready to tackle ${concept}!`,
          detail: "The curriculum planner detected high confidence on preceding topics, unlocking this new concept.",
        };
      case "REVIEW_DUE":
        return {
          title: "Retention Practice",
          color: "border-sky-500/30 bg-sky-500/10 text-sky-300",
          icon: "🔄",
          summary: `Scheduled spaced review for ${concept} to consolidate long-term retention.`,
          detail: "Spaced repetition intervals ensure knowledge sticks and doesn't decay over time.",
        };
      case "MISCONCEPTION_DETECTED":
        return {
          title: "Targeted Clarification",
          color: "border-rose-500/30 bg-rose-500/10 text-rose-300",
          icon: "🎯",
          summary: `Addressing a specific misunderstanding identified in your recent answers for ${concept}.`,
          detail: "Our diagnostic model detected an error pattern corresponding to a known DSA misconception.",
        };
      case "MISCONCEPTION_SUSPECTED":
        return {
          title: "Conceptual Alignment",
          color: "border-purple-500/30 bg-purple-500/10 text-purple-300",
          icon: "🔍",
          summary: `Reviewing ${concept} to ensure subtle edge-case behaviors are clear.`,
          detail: "Telemetry or rating signals indicated hesitation, prompting an interactive concept check.",
        };
      case "DIAGNOSTIC":
      default:
        return {
          title: "Diagnostic Baseline",
          color: "border-indigo-500/30 bg-indigo-500/10 text-indigo-300",
          icon: "🧭",
          summary: `Calibrating your initial knowledge baseline on ${concept}.`,
          detail: "Initial diagnostic responses calibrate our Bayesian Knowledge Tracing priors.",
        };
    }
  };

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4 sm:p-5 shadow-lg backdrop-blur-md space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-white">Why this recommendation?</span>
          <span className="text-[11px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 font-mono">
            Pedagogical Reasons
          </span>
        </div>
        <button
          type="button"
          onClick={() => setShowTechnical(!showTechnical)}
          className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors"
        >
          {showTechnical ? "Hide technical data" : "View model details"}
        </button>
      </div>

      <div className="space-y-2">
        {reasons.map((r, idx) => {
          const info = formatReason(r);
          return (
            <div
              key={`${r.code}-${r.concept_id}-${idx}`}
              className={`rounded-xl border p-3 text-xs space-y-1 ${info.color}`}
            >
              <div className="flex items-center justify-between font-medium">
                <span className="flex items-center gap-1.5">
                  <span>{info.icon}</span>
                  <span>{info.title}</span>
                </span>
                <span className="font-mono text-[10px] opacity-80 uppercase tracking-wider">
                  {r.code}
                </span>
              </div>
              <p className="text-slate-200 text-xs leading-relaxed">{info.summary}</p>
              {showTechnical && (
                <div className="pt-1.5 mt-1 border-t border-slate-800/60 font-mono text-[11px] text-slate-400 space-y-0.5">
                  <div>Model confidence / value: {r.value !== null && r.value !== undefined ? r.value.toFixed(3) : "N/A"}</div>
                  <div>Target Concept ID: {r.concept_id}</div>
                  <div>Note: {info.detail}</div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
