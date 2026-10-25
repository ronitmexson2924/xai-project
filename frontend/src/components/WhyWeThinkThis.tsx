"use client";

import React, { useState } from "react";
import type { StateUpdateView } from "@/lib/api";

interface WhyWeThinkThisProps {
  history: StateUpdateView[];
}

export default function WhyWeThinkThis({ history }: WhyWeThinkThisProps) {
  const [filter, setFilter] = useState<string>("all");

  const filteredHistory = history.filter((item) => {
    if (filter === "all") return true;
    return item.source === filter;
  });

  const getSourceBadge = (source: string) => {
    switch (source) {
      case "attempt":
        return {
          icon: "🎯",
          label: "Practice Attempt",
          color: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
        };
      case "questionnaire":
        return {
          icon: "📋",
          label: "Intake Questionnaire",
          color: "bg-indigo-500/20 text-indigo-300 border-indigo-500/30",
        };
      case "explanation_feedback":
        return {
          icon: "🔄",
          label: "Explanation Feedback",
          color: "bg-purple-500/20 text-purple-300 border-purple-500/30",
        };
      default:
        return {
          icon: "⚙️",
          label: source,
          color: "bg-slate-700 text-slate-300 border-slate-600",
        };
    }
  };

  return (
    <div className="rounded-3xl border border-white/10 bg-slate-900/60 p-6 sm:p-8 backdrop-blur-md shadow-xl">
      <div className="mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-white/5 pb-4">
        <div>
          <h2 className="text-lg sm:text-xl font-bold text-white flex items-center gap-2">
            <span>🔍</span> &ldquo;Why We Think This&rdquo; Audit Trail
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Complete provenance and audit log of every change to your mastery and cognitive traits.
          </p>
        </div>

        {/* Filter buttons */}
        <div className="flex flex-wrap gap-1.5 self-start sm:self-auto">
          {["all", "attempt", "explanation_feedback", "questionnaire"].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`text-[11px] font-semibold px-2.5 py-1 rounded-xl transition-all ${
                filter === f
                  ? "bg-indigo-600 text-white shadow-xs"
                  : "bg-slate-800 text-slate-400 hover:text-slate-200"
              }`}
            >
              {f === "all"
                ? `All (${history.length})`
                : f === "attempt"
                ? "Attempts"
                : f === "explanation_feedback"
                ? "Feedback"
                : "Survey"}
            </button>
          ))}
        </div>
      </div>

      {filteredHistory.length === 0 ? (
        <div className="text-center py-12 text-slate-500 text-xs">
          No audit entries recorded for this filter yet. Practice items or complete feedback to see updates.
        </div>
      ) : (
        <div className="space-y-3 relative before:absolute before:inset-0 before:left-4 before:h-full before:w-0.5 before:bg-slate-800 before:content-['']">
          {filteredHistory.map((entry) => {
            const badge = getSourceBadge(entry.source);
            const date = new Date(entry.created_at);
            const timeStr = date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

            return (
              <div
                key={entry.id}
                className="relative flex items-start gap-3.5 pl-2 group"
              >
                {/* Timeline Dot */}
                <span className="relative z-10 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-slate-900 border border-slate-700 text-xs">
                  {badge.icon}
                </span>

                {/* Card */}
                <div className="w-full rounded-2xl border border-slate-800/80 bg-slate-950/70 p-4 transition-colors group-hover:border-slate-700">
                  <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${badge.color}`}
                      >
                        {badge.label}
                      </span>
                      <span className="text-[11px] font-mono text-slate-400">
                        source_id: {entry.source_id}
                      </span>
                    </div>
                    <span className="text-[10px] font-mono text-slate-500">{timeStr}</span>
                  </div>

                  {/* Mastery deltas */}
                  {entry.delta.mastery_changes &&
                    Object.entries(entry.delta.mastery_changes).map(([cid, [before, after]]) => {
                      const diff = after - before;
                      const isPos = diff >= 0;
                      return (
                        <div
                          key={cid}
                          className="flex items-center gap-2 text-xs font-mono my-1 bg-slate-900/60 px-2.5 py-1 rounded-lg border border-white/5"
                        >
                          <span className="text-slate-300 font-semibold">{cid}:</span>
                          <span className="text-slate-400">{Math.round(before * 100)}%</span>
                          <span>→</span>
                          <span className={isPos ? "text-emerald-400 font-bold" : "text-rose-400 font-bold"}>
                            {Math.round(after * 100)}%
                          </span>
                          <span
                            className={`text-[10px] px-1 rounded ${
                              isPos
                                ? "bg-emerald-500/20 text-emerald-300"
                                : "bg-rose-500/20 text-rose-300"
                            }`}
                          >
                            {isPos ? `+${(diff * 100).toFixed(0)}%` : `${(diff * 100).toFixed(0)}%`}
                          </span>
                        </div>
                      );
                    })}

                  {/* Trait deltas */}
                  {entry.delta.trait_changes &&
                    Object.entries(entry.delta.trait_changes).map(([trait, [before, after]]) => {
                      const diff = after - before;
                      const isPos = diff >= 0;
                      return (
                        <div
                          key={trait}
                          className="flex items-center gap-2 text-xs font-mono my-1 bg-indigo-950/30 px-2.5 py-1 rounded-lg border border-indigo-500/20"
                        >
                          <span className="text-indigo-200 font-semibold">{trait}:</span>
                          <span className="text-slate-400">{before.toFixed(2)}</span>
                          <span>→</span>
                          <span className="text-indigo-300 font-bold">{after.toFixed(2)}</span>
                          <span
                            className={`text-[10px] px-1 rounded ${
                              isPos
                                ? "bg-indigo-500/20 text-indigo-300"
                                : "bg-purple-500/20 text-purple-300"
                            }`}
                          >
                            {isPos ? `+${diff.toFixed(2)}` : diff.toFixed(2)}
                          </span>
                        </div>
                      );
                    })}

                  {/* Notes */}
                  {entry.delta.notes && entry.delta.notes.length > 0 && (
                    <div className="mt-2 space-y-1">
                      {entry.delta.notes.map((note, i) => (
                        <p key={i} className="text-xs text-slate-300 leading-relaxed">
                          {note}
                        </p>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
