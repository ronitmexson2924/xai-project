"use client";

import React, { useMemo, useState } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  Edge,
  MarkerType,
  MiniMap,
  Node,
  Panel,
  ReactFlow,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import ConceptNode from "./ConceptNode";
import type { Concept, ConceptEdge, LearnerState } from "@/lib/api";

const CLUSTERS = [
  "all",
  "basics",
  "arrays-strings",
  "linked-structures",
  "recursion",
  "sorting-searching",
  "trees",
  "graphs",
  "dp",
];

const CLUSTER_POSITIONS: Record<string, { x: number; yOffset: number }> = {
  basics: { x: 50, yOffset: 50 },
  "arrays-strings": { x: 350, yOffset: 50 },
  "linked-structures": { x: 650, yOffset: 50 },
  recursion: { x: 950, yOffset: 50 },
  "sorting-searching": { x: 1250, yOffset: 50 },
  trees: { x: 1550, yOffset: 50 },
  graphs: { x: 1850, yOffset: 50 },
  dp: { x: 2150, yOffset: 50 },
};

interface ConceptGraphProps {
  concepts: Concept[];
  edges: ConceptEdge[];
  learnerState: LearnerState | null;
  onSelectConcept: (concept: Concept) => void;
  selectedConceptId?: string | null;
}

const nodeTypes = {
  conceptNode: ConceptNode,
};

export default function ConceptGraph({
  concepts,
  edges,
  learnerState,
  onSelectConcept,
  selectedConceptId,
}: ConceptGraphProps) {
  const [activeCluster, setActiveCluster] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");

  const filteredConcepts = useMemo(() => {
    return concepts.filter((c) => {
      const matchesCluster = activeCluster === "all" || c.cluster === activeCluster;
      const matchesSearch =
        searchQuery.trim() === "" ||
        c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        c.id.toLowerCase().includes(searchQuery.toLowerCase());
      return matchesCluster && matchesSearch;
    });
  }, [concepts, activeCluster, searchQuery]);

  const nodes: Node[] = useMemo(() => {
    const clusterCounters: Record<string, number> = {};

    return filteredConcepts.map((c) => {
      const posConfig = CLUSTER_POSITIONS[c.cluster] || { x: 100, yOffset: 100 };
      const idxInCluster = clusterCounters[c.cluster] || 0;
      clusterCounters[c.cluster] = idxInCluster + 1;

      const masteryData = learnerState?.mastery?.[c.id];
      const pMastery = masteryData?.p_mastery ?? 0.2;
      const uncertainty =
        (masteryData as { uncertainty?: number } | undefined)?.uncertainty ?? 0.25;
      const attempts = masteryData?.n_attempts ?? 0;
      const misconceptions = masteryData?.misconception_ids ?? [];

      return {
        id: c.id,
        type: "conceptNode",
        position: {
          x: posConfig.x,
          y: posConfig.yOffset + idxInCluster * 170,
        },
        data: {
          id: c.id,
          name: c.name,
          cluster: c.cluster,
          difficulty: c.difficulty,
          mastery: pMastery,
          uncertainty,
          misconceptions,
          attempts,
        },
        selected: c.id === selectedConceptId,
      };
    });
  }, [filteredConcepts, learnerState, selectedConceptId]);

  const flowEdges: Edge[] = useMemo(() => {
    const visibleIds = new Set(filteredConcepts.map((c) => c.id));
    return edges
      .filter((e) => visibleIds.has(e.src) && visibleIds.has(e.dst))
      .map((e) => ({
        id: `${e.src}->${e.dst}`,
        source: e.src,
        target: e.dst,
        animated: true,
        style: { stroke: "#6366f1", strokeWidth: 1.5, opacity: 0.6 },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: "#6366f1",
          width: 14,
          height: 14,
        },
      }));
  }, [edges, filteredConcepts]);

  const handleNodeClick = (_: React.MouseEvent, node: Node) => {
    const concept = concepts.find((c) => c.id === node.id);
    if (concept) onSelectConcept(concept);
  };

  return (
    <div className="relative h-[650px] w-full rounded-3xl border border-white/10 bg-slate-950/80 shadow-2xl overflow-hidden backdrop-blur-md">
      <ReactFlow
        nodes={nodes}
        edges={flowEdges}
        nodeTypes={nodeTypes}
        onNodeClick={handleNodeClick}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.2}
        maxZoom={1.8}
        className="bg-slate-950"
      >
        <Background variant={BackgroundVariant.Dots} gap={24} size={1.2} color="#1e293b" />
        <Controls className="!bg-slate-900 !border-slate-800 !text-slate-300 rounded-xl" />
        <MiniMap
          nodeColor={(n) => {
            const mastery = (n.data as { mastery?: number })?.mastery ?? 0.2;
            if (mastery >= 0.7) return "#10b981";
            if (mastery >= 0.4) return "#f59e0b";
            return "#f43f5e";
          }}
          className="!bg-slate-900/90 !border-slate-800 !rounded-xl"
        />

        {/* Top Control Bar with Filters & Search */}
        <Panel position="top-left" className="m-3 flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1 bg-slate-900/90 border border-slate-800/80 p-1.5 rounded-2xl backdrop-blur-md shadow-lg">
            <span className="text-[11px] font-bold text-slate-400 px-2 uppercase tracking-wider">
              Cluster:
            </span>
            <div className="flex flex-wrap gap-1">
              {CLUSTERS.map((cl) => {
                const isActive = activeCluster === cl;
                return (
                  <button
                    key={cl}
                    onClick={() => setActiveCluster(cl)}
                    className={`text-[11px] font-semibold px-2.5 py-1 rounded-xl transition-all ${
                      isActive
                        ? "bg-indigo-600 text-white shadow-xs"
                        : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
                    }`}
                  >
                    {cl === "all" ? "All (48)" : cl}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="bg-slate-900/90 border border-slate-800/80 rounded-2xl px-3 py-1.5 backdrop-blur-md shadow-lg flex items-center gap-2">
            <svg
              className="w-3.5 h-3.5 text-slate-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
            <input
              type="text"
              placeholder="Search concepts..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="bg-transparent text-xs text-white placeholder-slate-500 focus:outline-none w-36 sm:w-48"
            />
          </div>
        </Panel>

        {/* Legend Panel */}
        <Panel
          position="bottom-left"
          className="m-3 p-3 bg-slate-900/90 border border-slate-800/80 rounded-2xl backdrop-blur-md shadow-lg text-[11px] text-slate-300 flex items-center gap-4"
        >
          <div className="flex items-center gap-1.5">
            <span className="h-3 w-3 rounded-full bg-emerald-500" />
            <span>Mastered (≥70%)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="h-3 w-3 rounded-full bg-amber-500" />
            <span>Competent (40–69%)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="h-3 w-3 rounded-full bg-rose-500" />
            <span>Developing (&lt;40%)</span>
          </div>
          <div className="flex items-center gap-1.5 pl-2 border-l border-slate-800">
            <span className="h-3 w-3 rounded-full border-2 border-indigo-400 animate-pulse" />
            <span>Uncertainty Halo (σ &gt; 0.28)</span>
          </div>
        </Panel>
      </ReactFlow>
    </div>
  );
}
