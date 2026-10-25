"use client";

import React, { memo } from "react";
import { Handle, Position } from "@xyflow/react";

export interface ConceptNodeData {
  id: string;
  name: string;
  cluster: string;
  difficulty: number;
  mastery: number; // 0.0 to 1.0
  uncertainty: number; // 0.0 to 1.0
  misconceptions: string[];
  attempts: number;
}

interface ConceptNodeProps {
  data: ConceptNodeData;
  selected?: boolean;
}

function getMasteryTheme(p: number) {
  if (p >= 0.7) {
    return {
      border: "border-emerald-500/60",
      bg: "bg-emerald-950/40",
      text: "text-emerald-300",
      pill: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
      bar: "bg-emerald-400",
      label: "Mastered",
    };
  }
  if (p >= 0.4) {
    return {
      border: "border-amber-500/60",
      bg: "bg-amber-950/40",
      text: "text-amber-300",
      pill: "bg-amber-500/20 text-amber-300 border-amber-500/40",
      bar: "bg-amber-400",
      label: "Competent",
    };
  }
  return {
    border: "border-rose-500/60",
    bg: "bg-rose-950/40",
    text: "text-rose-300",
    pill: "bg-rose-500/20 text-rose-300 border-rose-500/40",
    bar: "bg-rose-400",
    label: "Developing",
  };
}

function getUncertaintyRing(u: number) {
  if (u > 0.28) {
    return "ring-4 ring-indigo-500/40 animate-pulse shadow-lg shadow-indigo-500/20";
  }
  if (u >= 0.15) {
    return "ring-2 ring-indigo-400/30";
  }
  return "ring-1 ring-white/10";
}

const CLUSTER_BADGES: Record<string, string> = {
  basics: "bg-blue-500/20 text-blue-300 border-blue-500/30",
  "arrays-strings": "bg-cyan-500/20 text-cyan-300 border-cyan-500/30",
  "linked-structures": "bg-violet-500/20 text-violet-300 border-violet-500/30",
  recursion: "bg-fuchsia-500/20 text-fuchsia-300 border-fuchsia-500/30",
  "sorting-searching": "bg-amber-500/20 text-amber-300 border-amber-500/30",
  trees: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
  graphs: "bg-teal-500/20 text-teal-300 border-teal-500/30",
  dp: "bg-rose-500/20 text-rose-300 border-rose-500/30",
};

export default memo(function ConceptNode({ data, selected }: ConceptNodeProps) {
  const theme = getMasteryTheme(data.mastery);
  const ringStyle = getUncertaintyRing(data.uncertainty);
  const clusterBadge =
    CLUSTER_BADGES[data.cluster] || "bg-slate-700/40 text-slate-300 border-slate-600/30";

  return (
    <div
      className={`relative min-w-[210px] max-w-[240px] rounded-2xl border p-3 backdrop-blur-md transition-all duration-200 cursor-pointer ${
        theme.bg
      } ${theme.border} ${ringStyle} ${
        selected ? "scale-105 border-indigo-400 shadow-xl shadow-indigo-500/30 ring-4 ring-indigo-400/50" : "hover:scale-[1.02]"
      }`}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!h-2.5 !w-2.5 !bg-indigo-400 !border-2 !border-slate-900"
      />

      {/* Cluster & Difficulty header */}
      <div className="flex items-center justify-between gap-1 mb-1.5">
        <span
          className={`text-[9px] font-semibold px-2 py-0.5 rounded-full border uppercase tracking-wider ${clusterBadge}`}
        >
          {data.cluster}
        </span>
        <span className="text-[10px] text-slate-400 font-mono">
          diff: {data.difficulty}/5
        </span>
      </div>

      {/* Concept Name */}
      <h3 className="text-xs font-bold text-slate-100 leading-snug line-clamp-2 mb-2">
        {data.name}
      </h3>

      {/* Mastery Progress Bar */}
      <div className="space-y-1">
        <div className="flex items-center justify-between text-[10px]">
          <span className={`font-semibold ${theme.text}`}>{theme.label}</span>
          <span className="font-mono text-slate-300 font-bold">
            {Math.round(data.mastery * 100)}%
          </span>
        </div>
        <div className="h-1.5 w-full rounded-full bg-slate-800/80 overflow-hidden border border-white/5">
          <div
            className={`h-full rounded-full transition-all duration-500 ${theme.bar}`}
            style={{ width: `${Math.max(6, Math.round(data.mastery * 100))}%` }}
          />
        </div>
      </div>

      {/* Footer Metrics & Uncertainty Indicators */}
      <div className="mt-2.5 pt-2 border-t border-white/5 flex items-center justify-between text-[9px] text-slate-400 font-mono">
        <span title="Uncertainty standard deviation (BKT)">
          σ: {(data.uncertainty).toFixed(2)}
        </span>
        {data.misconceptions && data.misconceptions.length > 0 ? (
          <span
            className="flex items-center gap-0.5 text-rose-400 bg-rose-500/10 px-1.5 py-0.5 rounded border border-rose-500/20 font-sans font-semibold"
            title={`Detected Misconception: ${data.misconceptions.join(", ")}`}
          >
            ⚠️ {data.misconceptions.length}
          </span>
        ) : (
          <span>{data.attempts} attempts</span>
        )}
      </div>

      <Handle
        type="source"
        position={Position.Bottom}
        className="!h-2.5 !w-2.5 !bg-emerald-400 !border-2 !border-slate-900"
      />
    </div>
  );
});
