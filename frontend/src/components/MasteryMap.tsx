"use client";

import { AnimatePresence, motion } from "motion/react";
import React, { useEffect, useMemo, useRef, useState } from "react";
import type { Concept, LearnerState } from "@/lib/api";
import { BAND_LABEL, band, CLUSTER_LABEL, type Band } from "@/lib/mastery";
import { BeliefPanel } from "./BeliefPanel";
import { Markdown } from "./Markdown";
import { Badge } from "./ui/Badge";
import { Card, SectionTitle } from "./ui/Card";
import { cn } from "./ui/cn";
import { ease } from "./ui/motion";

const TILE: Record<Band, string> = {
  new: "border-line bg-surface text-muted",
  learning: "border-warning/40 bg-warning-soft text-fg",
  progress: "border-primary/30 bg-primary-soft text-fg",
  ready: "border-primary/60 bg-primary-soft text-fg",
  mastered: "border-success/50 bg-success-soft text-fg",
};
const DOT: Record<Band, string> = {
  new: "bg-line-strong",
  learning: "bg-warning",
  progress: "bg-primary/60",
  ready: "bg-primary",
  mastered: "bg-success",
};

/** Every concept, grouped by cluster and coloured by estimated mastery. Select one to see why. */
export function MasteryMap({ concepts, state }: { concepts: Concept[]; state: LearnerState | null }) {
  const [open, setOpen] = useState<Concept | null>(null);
  const clusters = useMemo(() => {
    const groups = new Map<string, Concept[]>();
    for (const c of concepts) groups.set(c.cluster, [...(groups.get(c.cluster) ?? []), c]);
    return [...groups.entries()];
  }, [concepts]);

  return (
    <section className="space-y-4" aria-labelledby="map-title">
      <SectionTitle
        title="Your concept map"
        hint="What the app estimates you know. Select a concept to see why."
        action={
          <div className="hidden flex-wrap gap-3 md:flex" aria-label="Legend">
            {(["new", "learning", "progress", "ready", "mastered"] as Band[]).map((b) => (
              <span key={b} className="inline-flex items-center gap-1.5 text-xs text-muted">
                <span className={cn("h-2 w-2 rounded-full", DOT[b])} aria-hidden />
                {BAND_LABEL[b]}
              </span>
            ))}
          </div>
        }
      />
      <h2 id="map-title" className="sr-only">
        Concept map
      </h2>
      <Card className="divide-y divide-line">
        {clusters.map(([cluster, items], ci) => (
          <div key={cluster} className="grid gap-3 p-4 sm:grid-cols-[180px_1fr] sm:p-5">
            <h3 className="text-sm font-medium text-fg">{CLUSTER_LABEL[cluster] ?? cluster}</h3>
            <ul className="flex flex-wrap gap-2">
              {items.map((c, i) => {
                const m = state?.mastery?.[c.id];
                const b = band(m?.p_mastery ?? 0, m?.n_attempts ?? 0);
                return (
                  <motion.li
                    key={c.id}
                    initial={{ opacity: 0, scale: 0.94 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.3, ease, delay: Math.min(ci * 0.04 + i * 0.015, 0.6) }}
                  >
                    <button
                      type="button"
                      onClick={() => setOpen(c)}
                      className={cn(
                        "inline-flex items-center gap-2 rounded-lg border px-2.5 py-1.5 text-[13px] transition-all hover:-translate-y-px hover:shadow-card",
                        TILE[b]
                      )}
                      aria-label={`${c.name}: ${BAND_LABEL[b]}${m && m.n_attempts ? `, ${Math.round(m.p_mastery * 100)}%` : ""}`}
                    >
                      <span className={cn("h-1.5 w-1.5 rounded-full", DOT[b])} aria-hidden />
                      {c.name}
                    </button>
                  </motion.li>
                );
              })}
            </ul>
          </div>
        ))}
      </Card>
      <ConceptDrawer concept={open} state={state} onClose={() => setOpen(null)} />
    </section>
  );
}

function ConceptDrawer({ concept, state, onClose }: { concept: Concept | null; state: LearnerState | null; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement | null>(null);
  useEffect(() => {
    if (!concept) return;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [concept, onClose]);

  const m = concept ? state?.mastery?.[concept.id] : undefined;
  const b = band(m?.p_mastery ?? 0, m?.n_attempts ?? 0);
  return (
    <AnimatePresence>
      {concept && (
        <motion.div className="fixed inset-0 z-50 flex justify-end" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <button type="button" aria-label="Close" className="absolute inset-0 bg-black/30 backdrop-blur-[2px]" onClick={onClose} />
          <motion.aside
            role="dialog"
            aria-modal="true"
            aria-labelledby="drawer-title"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 320, damping: 34 }}
            className="relative flex h-full w-full max-w-md flex-col overflow-y-auto border-l border-line bg-surface p-6 shadow-pop"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-medium text-subtle">{CLUSTER_LABEL[concept.cluster] ?? concept.cluster}</p>
                <h2 id="drawer-title" className="mt-1 text-xl font-semibold tracking-tight text-fg">
                  {concept.name}
                </h2>
              </div>
              <button ref={closeRef} type="button" onClick={onClose} className="rounded-lg p-1.5 text-muted hover:bg-surface-2 hover:text-fg" aria-label="Close">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden>
                  <path d="M6 6l12 12M18 6 6 18" />
                </svg>
              </button>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <Badge tone={b === "mastered" ? "success" : b === "learning" ? "warning" : b === "new" ? "neutral" : "primary"}>{BAND_LABEL[b]}</Badge>
              <Badge>{m?.n_attempts ?? 0} answers</Badge>
            </div>
            <p className="mt-5 text-sm leading-relaxed text-muted">{concept.description}</p>

            <div className="mt-6 rounded-xl border border-line bg-surface-2 p-4">
              <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-subtle">Why we think this</h3>
              <BeliefPanel subject={concept.id} />
            </div>

            <div className="mt-6 space-y-2">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-subtle">Key idea</h3>
              <Markdown text={concept.card.key_idea} className="text-sm text-fg" />
            </div>
            <div className="mt-6 space-y-2">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-subtle">Common pitfall</h3>
              <Markdown text={concept.card.pitfall} className="text-sm text-muted" />
            </div>
          </motion.aside>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
