"use client";

import Link from "next/link";
import React, { useCallback, useEffect, useState } from "react";
import { ChangeNotice } from "@/components/ChangeNotice";
import { ExplanationCard } from "@/components/ExplanationCard";
import { ItemCard } from "@/components/ItemCard";
import { api, ApiException, AttemptResult, ChangeNotice as ChangeNoticeData, NextStepResponse } from "@/lib/api";
import { useLearnerGuard } from "@/lib/guards";
import { useConcepts } from "@/lib/useConcepts";

/**
 * One learning step. Practice: the explanation (with "Why this?") comes first and the question is
 * its micro-check. Placement (diagnostic) questions come first, so the explanation cannot give the
 * answer away; their explanation follows the answer.
 */
export default function SessionPage() {
  const ready = useLearnerGuard();
  const concepts = useConcepts();

  const [step, setStep] = useState<NextStepResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<AttemptResult | null>(null);
  const [closeNotice, setCloseNotice] = useState<ChangeNoticeData | null>(null);
  const [lastAnswer, setLastAnswer] = useState<string | null>(null);
  const [answered, setAnswered] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const loadNext = useCallback(async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    setCloseNotice(null);
    setLastAnswer(null);
    try {
      setStep(await api.session.next());
    } catch (err) {
      setError(err instanceof ApiException ? err.message : "Could not load the next question.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!ready) return;
    const timer = setTimeout(() => void loadNext(), 0);
    return () => clearTimeout(timer);
  }, [ready, loadNext]);

  const submit = async (response: string, latencyMs: number) => {
    if (!step?.item) return;
    setSubmitting(true);
    setError(null);
    setLastAnswer(response);
    try {
      const res = await api.attempts.submit({
        item_id: step.item.id,
        response,
        latency_ms: latencyMs,
        hints_used: 0,
        recommendation_id: step.recommendation.id,
        explanation_id: step.explanation.id,
      });
      setResult(res);
      setAnswered((n) => n + 1);
    } catch (err) {
      if (err instanceof ApiException && err.code === "ALREADY_ANSWERED") {
        await loadNext(); // answered in another tab: move on
        return;
      }
      setError(err instanceof ApiException ? err.message : "Could not submit your answer.");
    } finally {
      setSubmitting(false);
    }
  };

  const next = async () => {
    if (step) {
      try {
        // closes the explanation's feedback (a no-op if the micro-check already did)
        const feedback = await api.explanations.close(step.explanation.id);
        if (feedback.change?.messages.length) setCloseNotice(feedback.change);
      } catch {
        // feedback is best effort; never block the learner on it
      }
    }
    await loadNext();
  };

  if (!ready) {
    return <div className="flex min-h-screen items-center justify-center text-slate-400 text-sm">Loading…</div>;
  }

  const placement = step?.recommendation.kind === "diagnostic_item";
  const concept = step ? concepts[step.recommendation.target_concept_id] : undefined;
  const explanationFirst = Boolean(step && !placement);
  const showExplanation = Boolean(step && (explanationFirst || result || !step.item));

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-900/80 sticky top-0 z-40">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          <Link href="/" className="text-xs text-slate-400 hover:text-white">
            ← Home
          </Link>
          <span className="text-xs text-slate-400" data-testid="answered-count">
            Answered this session: <strong className="text-indigo-300">{answered}</strong>
          </span>
        </div>
      </header>

      <main className="flex-1 max-w-4xl w-full mx-auto px-4 sm:px-6 py-6 space-y-6">
        {error && (
          <div role="alert" className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-xs text-rose-300 flex items-center justify-between gap-3">
            <span>{error}</span>
            <button type="button" onClick={loadNext} className="px-3 py-1 rounded-lg bg-rose-500/20 hover:bg-rose-500/30">
              Retry
            </button>
          </div>
        )}

        <ChangeNotice notice={closeNotice} />

        {loading && (
          <div className="rounded-3xl border border-slate-800 bg-slate-900/50 p-12 text-center text-sm text-slate-300">
            Choosing your next step…
          </div>
        )}

        {!loading && step && (
          <div className="space-y-6">
            {placement && !result && (
              <p className="text-xs text-slate-400" data-testid="placement-note">
                Placement question: answer what you can, it helps us start at the right level.
              </p>
            )}

            {explanationFirst && showExplanation && (
              <ExplanationCard explanation={step.explanation} concept={concept} />
            )}

            {step.item && (
              <ItemCard
                item={step.item}
                conceptName={concept?.name}
                onAnswer={submit}
                isSubmitting={submitting}
                disabled={result !== null}
                selectedAnswer={lastAnswer}
                isCorrect={result?.correct}
              />
            )}

            {result && (
              <div
                data-testid="attempt-result"
                className={`rounded-2xl border p-5 ${
                  result.correct
                    ? "border-emerald-500/30 bg-emerald-950/30 text-emerald-100"
                    : "border-rose-500/30 bg-rose-950/30 text-rose-100"
                }`}
              >
                <h4 className="text-sm font-bold">{result.correct ? "Correct." : "Not quite."}</h4>
                {!result.correct && result.correct_answer && (
                  <p className="text-xs text-slate-300 mt-1">The expected answer: {result.correct_answer}</p>
                )}
              </div>
            )}

            <ChangeNotice notice={result?.change} />

            {!explanationFirst && showExplanation && (
              <ExplanationCard explanation={step.explanation} concept={concept} />
            )}

            {(result || !step.item) && (
              <div className="flex justify-end">
                <button
                  type="button"
                  onClick={next}
                  className="px-6 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-sm"
                >
                  Continue →
                </button>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
