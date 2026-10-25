"use client";

import Link from "next/link";
import React, { useEffect, useState } from "react";

import ConceptDetailModal from "@/components/ConceptDetailModal";
import ConceptGraph from "@/components/ConceptGraph";
import Navbar from "@/components/Navbar";
import { useLearnerGuard } from "@/lib/guards";
import TraitCard from "@/components/TraitCard";
import WhyWeThinkThis from "@/components/WhyWeThinkThis";
import {
  api,
  Concept,
  ConceptEdge,
  LearnerState,
  StateUpdateView,
} from "@/lib/api";

export default function DashboardPage() {
  const ready = useLearnerGuard();
  const [learnerState, setLearnerState] = useState<LearnerState | null>(null);
  const [history, setHistory] = useState<StateUpdateView[]>([]);
  const [concepts, setConcepts] = useState<Concept[]>([]);
  const [edges, setEdges] = useState<ConceptEdge[]>([]);
  const [selectedConcept, setSelectedConcept] = useState<Concept | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ready) return;
    let mounted = true;

    async function fetchData() {
      try {
        setLoading(true);
        setError(null);

        const [state, hist, graphData] = await Promise.all([
          api.learners.getState().catch((err) => {
            console.error("Failed to load learner state", err);
            return null;
          }),
          api.learners.getHistory().catch((err) => {
            console.error("Failed to load audit history", err);
            return [];
          }),
          api.graph.get().catch((err) => {
            console.error("Failed to load graph", err);
            return { concepts: [], edges: [] };
          }),
        ]);

        if (mounted) {
          setLearnerState(state);
          setHistory(hist);
          setConcepts(graphData.concepts);
          setEdges(graphData.edges);
        }
      } catch (err: unknown) {
        if (mounted) {
          setError(err instanceof Error ? err.message : "Failed to load dashboard data");
        }
      } finally {
        if (mounted) setLoading(false);
      }
    }

    fetchData();

    return () => {
      mounted = false;
    };
  }, [ready]);

  const masteredCount = Object.values(learnerState?.mastery || {}).filter(
    (m) => m.p_mastery >= 0.7
  ).length;

  const inProgressCount = Object.values(learnerState?.mastery || {}).filter(
    (m) => m.p_mastery >= 0.4 && m.p_mastery < 0.7
  ).length;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <Navbar />

      <main className="flex-1 mx-auto w-full max-w-7xl px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Dashboard Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 border-b border-white/10 pb-6">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                Open Learner Model
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight">
              Knowledge Graph &amp; Trait Model
            </h1>
            <p className="text-xs sm:text-sm text-slate-400 mt-1 max-w-2xl">
              Your estimated mastery of every concept, how sure the app is, and the record of every answer and rating that changed it. Select a concept to see why we think what we think.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Link
              href="/session"
              className="px-5 py-2.5 text-xs font-bold text-white bg-gradient-to-r from-indigo-500 to-emerald-500 rounded-xl hover:opacity-90 transition-opacity shadow-lg shadow-indigo-500/25 flex items-center gap-1.5"
            >
              <span>Practice DSA</span>
              <span>→</span>
            </Link>
          </div>
        </div>

        {/* Overview Stats Bar */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="rounded-2xl border border-white/5 bg-slate-900/60 p-4">
            <div className="text-[11px] text-slate-400 font-medium">Concepts Mastered</div>
            <div className="text-2xl font-black text-emerald-400 font-mono mt-1">
              {masteredCount}
              <span className="text-xs font-normal text-slate-500 ml-1">/ {concepts.length || 48}</span>
            </div>
          </div>

          <div className="rounded-2xl border border-white/5 bg-slate-900/60 p-4">
            <div className="text-[11px] text-slate-400 font-medium">In Progress</div>
            <div className="text-2xl font-black text-amber-400 font-mono mt-1">
              {inProgressCount}
            </div>
          </div>

          <div className="rounded-2xl border border-white/5 bg-slate-900/60 p-4">
            <div className="text-[11px] text-slate-400 font-medium">Practice Attempts</div>
            <div className="text-2xl font-black text-indigo-300 font-mono mt-1">
              {learnerState?.total_attempts ?? 0}
            </div>
          </div>

          <div className="rounded-2xl border border-white/5 bg-slate-900/60 p-4">
            <div className="text-[11px] text-slate-400 font-medium">Logged Provenance Events</div>
            <div className="text-2xl font-black text-slate-200 font-mono mt-1">
              {history.length}
            </div>
          </div>
        </div>

        {loading ? (
          <div className="flex flex-col items-center justify-center py-24 space-y-4">
            <div className="h-10 w-10 animate-spin rounded-full border-4 border-indigo-500 border-t-transparent" />
            <p className="text-xs text-slate-400">Loading Open Learner Model graph &amp; traits...</p>
          </div>
        ) : error ? (
          <div className="rounded-2xl border border-rose-500/30 bg-rose-950/20 p-6 text-center text-rose-300 text-xs">
            {error}
          </div>
        ) : (
          <>
            {/* Interactive Concept Graph */}
            <section className="space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-base sm:text-lg font-bold text-white flex items-center gap-2">
                    <span>🌐</span> Interactive Curriculum DAG
                  </h2>
                  <p className="text-xs text-slate-400">
                    Click any concept node to view definition, worked examples, common pitfalls, and detected misconceptions.
                  </p>
                </div>
              </div>

              <ConceptGraph
                concepts={concepts}
                edges={edges}
                learnerState={learnerState}
                onSelectConcept={(c) => setSelectedConcept(c)}
                selectedConceptId={selectedConcept?.id}
              />
            </section>

            {/* Plain-Language Traits Section */}
            {learnerState?.traits && (
              <section>
                <TraitCard traits={learnerState.traits} />
              </section>
            )}

            {/* Why We Think This Audit Section */}
            <section>
              <WhyWeThinkThis history={history} />
            </section>
          </>
        )}
      </main>

      {/* Concept Detail Drawer / Modal */}
      <ConceptDetailModal
        concept={selectedConcept}
        learnerState={learnerState}
        onClose={() => setSelectedConcept(null)}
      />
    </div>
  );
}
