"use client";

import React, { useState } from "react";
import { Explanation } from "@/lib/api";
import { useExplanationTelemetry } from "@/lib/useExplanationTelemetry";
import { ClarityPrompt } from "./ClarityPrompt";

interface ExplanationCardProps {
  explanation: Explanation;
  onDismiss?: () => void;
  showTelemetryDebug?: boolean;
}

export function ExplanationCard({
  explanation,
  onDismiss,
  showTelemetryDebug = false,
}: ExplanationCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [replaying, setReplaying] = useState(false);

  const {
    ref,
    activeDwellMs,
    trackExpanded,
    trackCollapsed,
    trackReplayed,
    trackClarityRated,
    trackDismissed,
  } = useExplanationTelemetry(explanation.id);

  const toggleExpand = () => {
    if (!expanded) {
      setExpanded(true);
      trackExpanded();
    } else {
      setExpanded(false);
      trackCollapsed();
    }
  };

  const handleReplay = () => {
    setReplaying(true);
    trackReplayed();
    setTimeout(() => {
      setReplaying(false);
    }, 1200);
  };

  const handleDismiss = () => {
    trackDismissed();
    if (onDismiss) {
      onDismiss();
    }
  };

  return (
    <div
      ref={ref}
      className={`rounded-2xl border border-slate-800 bg-slate-900/90 p-5 sm:p-6 shadow-xl backdrop-blur-xl space-y-4 transition-all duration-300 ${
        replaying ? "ring-2 ring-indigo-500/50 bg-indigo-950/20" : ""
      }`}
    >
      {/* Header with Style Badges */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-800/80">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-indigo-500 animate-pulse" />
          <h3 className="text-sm font-semibold text-white">
            Concept Explanation:{" "}
            <span className="font-mono text-indigo-300">
              {explanation.concept_ids.join(", ")}
            </span>
          </h3>
        </div>

        <div className="flex flex-wrap items-center gap-1.5 text-[11px] font-mono">
          <span className="px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            {explanation.style.example_first ? "example-first" : "rule-first"}
          </span>
          <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
            {explanation.style.length}
          </span>
          <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
            {explanation.style.depth}
          </span>
          <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            src:{explanation.source}
          </span>
        </div>
      </div>

      {/* Explanation Body */}
      <div className="text-sm text-slate-200 leading-relaxed space-y-3 font-normal whitespace-pre-line">
        {explanation.body_markdown}
      </div>

      {/* Expandable Worked Example or Deep Dive */}
      {expanded && (
        <div className="p-4 rounded-xl bg-slate-950/70 border border-indigo-500/20 space-y-2 text-xs text-slate-300 animate-in fade-in slide-in-from-top-2 duration-200">
          <div className="font-semibold text-indigo-300 flex items-center gap-1.5">
            <span>🔍 Deep Invariant Detail</span>
          </div>
          <p className="leading-relaxed">
            In recursive and graph algorithms, the base case or termination invariant guarantees
            well-founded induction: every step strictly reduces distance to the base case, preventing
            cyclic infinite branches.
          </p>
        </div>
      )}

      {/* Action Controls */}
      <div className="pt-2 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={toggleExpand}
            className="text-xs font-medium px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-colors"
          >
            {expanded ? "Collapse details ▲" : "Expand deep-dive ▼"}
          </button>

          <button
            type="button"
            onClick={handleReplay}
            disabled={replaying}
            className="text-xs font-medium px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-colors flex items-center gap-1"
          >
            <span>🔄</span>
            <span>{replaying ? "Replaying..." : "Replay walkthrough"}</span>
          </button>
        </div>

        {onDismiss && (
          <button
            type="button"
            onClick={handleDismiss}
            className="text-xs text-slate-400 hover:text-white px-2 py-1 transition-colors"
          >
            Dismiss card
          </button>
        )}
      </div>

      {/* 1-Tap Clarity Prompt */}
      <div className="pt-2">
        <ClarityPrompt
          explanationId={explanation.id}
          onRate={trackClarityRated}
        />
      </div>

      {/* Telemetry Dwell Metric (Development / Auditing) */}
      {showTelemetryDebug && (
        <div className="pt-2 border-t border-slate-800/60 flex items-center justify-between text-[11px] text-slate-500 font-mono">
          <span>Active Viewport Dwell: {(activeDwellMs / 1000).toFixed(1)}s</span>
          <span>Module C Telemetry: Active</span>
        </div>
      )}
    </div>
  );
}
