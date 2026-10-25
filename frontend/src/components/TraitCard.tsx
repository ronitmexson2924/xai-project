"use client";

import React from "react";
import type { LearnerState } from "@/lib/api";

interface TraitCardProps {
  traits: LearnerState["traits"];
}

interface TraitDescriptor {
  title: string;
  icon: string;
  plainLanguage: (mean: number) => string;
  pedagogicalImpact: string;
}

const TRAIT_DESCRIPTORS: Record<string, TraitDescriptor> = {
  abstraction_preference: {
    title: "Learning Structure",
    icon: "🧩",
    plainLanguage: (m) =>
      m < 0.4
        ? "You seem to learn best from concrete, worked code examples first, then generalizing."
        : m > 0.6
        ? "You seem to learn best when given high-level formal rules and operational invariants first."
        : "You comfortably balance both concrete code examples and abstract theoretical rules.",
    pedagogicalImpact:
      "The explainer places worked code examples before definition text when this indicates example-first.",
  },
  load_tolerance: {
    title: "Explanation Density",
    icon: "⚡",
    plainLanguage: (m) =>
      m < 0.4
        ? "You absorb technical explanations most effectively in focused, bite-sized portions."
        : m > 0.6
        ? "You thrive on comprehensive, dense technical breakdowns without simplified chunking."
        : "You handle standard explanation lengths with balanced detail.",
    pedagogicalImpact:
      "Controls length and sentence chunking: keeps explanations concise when cognitive load is elevated.",
  },
  depth_preference: {
    title: "Conceptual Focus",
    icon: "🔬",
    plainLanguage: (m) =>
      m < 0.4
        ? "You focus primarily on actionable execution mechanics ('how does the code run')."
        : m > 0.6
        ? "You seek deep foundational principles and theoretical motivation ('why does this hold')."
        : "You appreciate both implementation mechanics and conceptual justification.",
    pedagogicalImpact:
      "Controls whether explanations emphasize runtime pointers and loops or mathematical invariants.",
  },
  persistence: {
    title: "Problem Endurance",
    icon: "🛡️",
    plainLanguage: (m) =>
      m < 0.4
        ? "You benefit from quick feedback checkpoints and structured incremental hints."
        : m > 0.6
        ? "You show high perseverance, methodically testing tricky boundary conditions."
        : "You demonstrate steady persistence through standard multi-step algorithmic problems.",
    pedagogicalImpact:
      "Used by the planner to modulate recommendation difficulty leaps and hint availability.",
  },
  self_efficacy: {
    title: "DSA Confidence",
    icon: "🚀",
    plainLanguage: (m) =>
      m < 0.4
        ? "Building foundational problem-solving intuition and confidence in core DSA concepts."
        : m > 0.6
        ? "Strong confidence in analyzing, synthesizing, and optimizing complex algorithms."
        : "Growing confidence across intermediate algorithmic patterns and structures.",
    pedagogicalImpact:
      "Calibrates micro-check difficulty and formative feedback encouragement tone.",
  },
};

function getConfidenceLabel(variance: number) {
  if (variance < 0.02) {
    return { label: "high confidence", color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20" };
  }
  if (variance <= 0.05) {
    return { label: "moderately confident", color: "text-indigo-300 bg-indigo-500/10 border-indigo-500/20" };
  }
  return { label: "calibrating", color: "text-amber-400 bg-amber-500/10 border-amber-500/20" };
}

export default function TraitCard({ traits }: TraitCardProps) {
  if (!traits || !traits.traits) return null;

  return (
    <div className="rounded-3xl border border-white/10 bg-slate-900/60 p-6 sm:p-8 backdrop-blur-md shadow-xl">
      <div className="mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-white/5 pb-4">
        <div>
          <h2 className="text-lg sm:text-xl font-bold text-white flex items-center gap-2">
            <span>🧠</span> Plain-Language Learning Profile
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            How our Explainable AI models your cognitive preferences — grounded in validated psychometrics, not arbitrary labels.
          </p>
        </div>
        <span className="text-[11px] font-mono text-slate-400 bg-slate-800/80 px-2.5 py-1 rounded-xl self-start border border-slate-700/60">
          version: {traits.version}
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {Object.entries(traits.traits).map(([traitName, est]) => {
          const desc = TRAIT_DESCRIPTORS[traitName] || {
            title: traitName,
            icon: "📊",
            plainLanguage: (m: number) => `Trait estimate mean: ${m.toFixed(2)}`,
            pedagogicalImpact: "Feeds into adaptive explanation generation.",
          };
          const conf = getConfidenceLabel(est.variance);

          return (
            <div
              key={traitName}
              className="flex flex-col justify-between rounded-2xl border border-slate-800 bg-slate-950/60 p-5 hover:border-slate-700 transition-colors"
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className="text-xl">{desc.icon}</span>
                    <h3 className="text-sm font-bold text-white">{desc.title}</h3>
                  </div>
                  <span
                    className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${conf.color}`}
                  >
                    {conf.label}
                  </span>
                </div>

                {/* Plain-Language Insight */}
                <p className="text-xs font-medium text-slate-200 leading-relaxed mb-4">
                  &ldquo;{desc.plainLanguage(est.mean)}&rdquo;
                </p>
              </div>

              <div className="pt-3 border-t border-white/5 space-y-2">
                <div className="flex items-center justify-between text-[10px] text-slate-400 font-mono">
                  <span>mean: {est.mean.toFixed(2)}</span>
                  <span>obs: {est.n_observations}</span>
                  <span>var: {est.variance.toFixed(3)}</span>
                </div>
                <div className="text-[10px] text-slate-400 leading-normal italic">
                  💡 {desc.pedagogicalImpact}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
