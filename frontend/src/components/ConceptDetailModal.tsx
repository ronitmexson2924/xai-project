"use client";

import Link from "next/link";
import React from "react";
import type { Concept, LearnerState } from "@/lib/api";

interface ConceptDetailModalProps {
  concept: Concept | null;
  learnerState: LearnerState | null;
  onClose: () => void;
}

export default function ConceptDetailModal({
  concept,
  learnerState,
  onClose,
}: ConceptDetailModalProps) {
  if (!concept) return null;

  const masteryData = learnerState?.mastery?.[concept.id];
  const pMastery = masteryData?.p_mastery ?? 0.2;
  const uncertainty = (masteryData as { uncertainty?: number } | undefined)?.uncertainty ?? 0.25;
  const attempts = masteryData?.n_attempts ?? 0;
  const misconceptions = masteryData?.misconception_ids ?? [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-in fade-in duration-200">
      <div className="relative w-full max-w-2xl rounded-3xl border border-slate-700/80 bg-slate-900/95 p-6 sm:p-8 shadow-2xl shadow-indigo-950/50 max-h-[90vh] overflow-y-auto">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-5 right-5 text-slate-400 hover:text-white rounded-full p-1.5 hover:bg-slate-800 transition-colors"
          aria-label="Close details"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        {/* Header */}
        <div className="flex flex-wrap items-center gap-2 mb-3">
          <span className="text-xs font-bold uppercase tracking-wider px-2.5 py-1 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
            {concept.cluster}
          </span>
          <span className="text-xs text-slate-400 font-mono">
            Difficulty {concept.difficulty}/5
          </span>
          {misconceptions.length > 0 && (
            <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/30 flex items-center gap-1">
              ⚠️ {misconceptions.length} Active Misconception
            </span>
          )}
        </div>

        <h2 className="text-xl sm:text-2xl font-black text-white tracking-tight mb-2">
          {concept.name}
        </h2>
        <p className="text-xs sm:text-sm text-slate-300 mb-6">{concept.description}</p>

        {/* Open Learner Model Stats Row */}
        <div className="grid grid-cols-3 gap-3 p-4 rounded-2xl bg-slate-800/50 border border-slate-700/60 mb-6 text-center">
          <div>
            <div className="text-[11px] text-slate-400 font-medium">BKT Mastery</div>
            <div className="text-lg font-black text-emerald-400 font-mono">
              {Math.round(pMastery * 100)}%
            </div>
          </div>
          <div>
            <div className="text-[11px] text-slate-400 font-medium">Uncertainty (σ)</div>
            <div className="text-lg font-black text-indigo-300 font-mono">
              {uncertainty.toFixed(2)}
            </div>
          </div>
          <div>
            <div className="text-[11px] text-slate-400 font-medium">Attempts Logged</div>
            <div className="text-lg font-black text-slate-200 font-mono">{attempts}</div>
          </div>
        </div>

        {/* Misconception Warning Banner if applicable */}
        {misconceptions.length > 0 && (
          <div className="mb-6 rounded-2xl border border-rose-500/40 bg-rose-950/30 p-4 text-xs text-rose-200">
            <div className="font-bold text-rose-300 mb-1 flex items-center gap-1.5">
              <span>⚠️</span> Misconception Detected
            </div>
            <p>
              Your recent attempts indicated a possible misconception ({misconceptions.join(", ")}).
              The adaptive explainer is tailoring upcoming exercises to remediate this conceptual gap.
            </p>
          </div>
        )}

        {/* Concept Card Content */}
        {concept.card && (
          <div className="space-y-4 text-xs sm:text-sm">
            <div className="rounded-2xl bg-slate-800/40 border border-slate-700/40 p-4">
              <div className="text-[11px] font-bold uppercase tracking-wider text-indigo-400 mb-1">
                Definition
              </div>
              <p className="text-slate-200 leading-relaxed">{concept.card.definition}</p>
            </div>

            <div className="rounded-2xl bg-slate-800/40 border border-slate-700/40 p-4">
              <div className="text-[11px] font-bold uppercase tracking-wider text-emerald-400 mb-1">
                Key Invariant
              </div>
              <p className="text-slate-200 leading-relaxed">{concept.card.key_idea}</p>
            </div>

            {concept.card.worked_example && (
              <div className="rounded-2xl bg-slate-950 border border-slate-800 p-4">
                <div className="text-[11px] font-bold uppercase tracking-wider text-cyan-400 mb-2">
                  Worked Example
                </div>
                <pre className="font-mono text-xs text-cyan-200 bg-slate-900/80 p-3 rounded-xl overflow-x-auto border border-white/5 whitespace-pre-wrap">
                  {concept.card.worked_example}
                </pre>
              </div>
            )}

            {concept.card.pitfall && (
              <div className="rounded-2xl bg-amber-950/20 border border-amber-500/30 p-4">
                <div className="text-[11px] font-bold uppercase tracking-wider text-amber-400 mb-1">
                  Common Pitfall
                </div>
                <p className="text-amber-200/90 leading-relaxed">{concept.card.pitfall}</p>
              </div>
            )}
          </div>
        )}

        {/* Footer Actions */}
        <div className="mt-8 pt-4 border-t border-slate-800 flex items-center justify-between">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold text-slate-300 hover:text-white rounded-xl hover:bg-slate-800 transition-colors"
          >
            Close
          </button>
          <Link
            href="/session"
            className="px-5 py-2.5 text-xs font-bold text-white bg-gradient-to-r from-indigo-500 to-emerald-500 rounded-xl hover:opacity-90 transition-opacity shadow-lg shadow-indigo-500/20"
          >
            Practice In Adaptive Session →
          </Link>
        </div>
      </div>
    </div>
  );
}
