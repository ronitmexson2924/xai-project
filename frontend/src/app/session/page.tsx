"use client";

import { AnimatePresence, motion } from "motion/react";
import React, { useCallback, useEffect, useState } from "react";
import { AppShell, PageLoading } from "@/components/AppShell";
import { ChangeNotice } from "@/components/ChangeNotice";
import { ExplanationCard } from "@/components/ExplanationCard";
import { ItemCard } from "@/components/ItemCard";
import { Badge } from "@/components/ui/Badge";
import { Button, Spinner } from "@/components/ui/Button";
import { ease } from "@/components/ui/motion";
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

  if (!ready) return <PageLoading />;

  const placement = step?.recommendation.kind === "diagnostic_item";
  const concept = step ? concepts[step.recommendation.target_concept_id] : undefined;
  const explanationFirst = Boolean(step && !placement);
  const showExplanation = Boolean(step && (explanationFirst || result || !step.item));

  return (
    <AppShell>
      <div className="mx-auto max-w-3xl space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-fg">Learn</h1>
            <p className="text-sm text-muted">One step at a time. Each step is chosen from what you know now.</p>
          </div>
          <span
            className="inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1 text-sm text-muted"
            data-testid="answered-count"
          >
            Answered this session
            <motion.strong key={answered} initial={{ scale: 1.4 }} animate={{ scale: 1 }} className="tabular-nums text-fg">
              {answered}
            </motion.strong>
          </span>
        </div>

        {error && (
          <div role="alert" className="flex items-center justify-between gap-3 rounded-xl border border-danger/30 bg-danger-soft p-4 text-sm text-danger">
            <span>{error}</span>
            <Button size="sm" variant="secondary" onClick={loadNext}>
              Retry
            </Button>
          </div>
        )}

        <ChangeNotice notice={closeNotice} />

        <AnimatePresence mode="wait">
          {loading ? (
            <motion.div
              key="loading"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex flex-col items-center gap-3 rounded-2xl border border-line bg-surface p-12 text-sm text-muted"
              aria-busy
            >
              <Spinner className="text-accent" />
              Choosing your next step…
            </motion.div>
          ) : step ? (
            <motion.div
              key={step.recommendation.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.35, ease }}
              className="space-y-5"
            >
              {placement && !result && (
                <p className="flex items-center gap-2 text-sm text-muted" data-testid="placement-note">
                  <Badge tone="warning">Placement</Badge>
                  Answer what you can. It helps us start at the right level.
                </p>
              )}

              {explanationFirst && showExplanation && <ExplanationCard explanation={step.explanation} concept={concept} />}

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

              <AnimatePresence>
                {result && (
                  <motion.div
                    data-testid="attempt-result"
                    initial={{ opacity: 0, scale: 0.97 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ type: "spring", stiffness: 400, damping: 28 }}
                    className={`flex items-start gap-3 rounded-2xl border p-5 ${
                      result.correct ? "border-success/40 bg-success-soft" : "border-danger/40 bg-danger-soft"
                    }`}
                  >
                    <span
                      className={`flex h-7 w-7 flex-none items-center justify-center rounded-full text-white ${result.correct ? "bg-success" : "bg-danger"}`}
                      aria-hidden
                    >
                      {result.correct ? "✓" : "✕"}
                    </span>
                    <div>
                      <h2 className="font-semibold text-fg">{result.correct ? "Correct." : "Not quite."}</h2>
                      {!result.correct && result.correct_answer && (
                        <p className="mt-0.5 text-sm text-muted">
                          The expected answer: <span className="font-medium text-fg">{result.correct_answer}</span>
                        </p>
                      )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              <ChangeNotice notice={result?.change} />

              {!explanationFirst && showExplanation && <ExplanationCard explanation={step.explanation} concept={concept} />}

              {(result || !step.item) && (
                <div className="sticky bottom-4 flex justify-end">
                  <Button size="lg" onClick={next} className="shadow-pop">
                    Continue <span aria-hidden>→</span>
                  </Button>
                </div>
              )}
            </motion.div>
          ) : null}
        </AnimatePresence>
      </div>
    </AppShell>
  );
}
