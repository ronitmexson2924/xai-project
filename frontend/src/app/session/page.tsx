"use client";

import { AnimatePresence, motion } from "motion/react";
import React, { useCallback, useEffect, useRef, useState } from "react";
import { AppShell, PageLoading } from "@/components/AppShell";
import { ChangeNotice } from "@/components/ChangeNotice";
import { ExplanationCard } from "@/components/ExplanationCard";
import { ItemCard } from "@/components/ItemCard";
import { MasteryMeter } from "@/components/session/MasteryMeter";
import { ResultMoment } from "@/components/session/ResultMoment";
import { SessionRecap } from "@/components/session/SessionRecap";
import { SessionStrip } from "@/components/session/SessionStrip";
import { ModelInsightPanel } from "@/components/xai/ModelInsightPanel";
import { Badge } from "@/components/ui/Badge";
import { Button, Spinner } from "@/components/ui/Button";
import { ease } from "@/components/ui/motion";
import { api, ApiException, AttemptResult, ChangeNotice as ChangeNoticeData, ModelInsight, NextStepResponse } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { ENGAGEMENT_UI, RECAP_EVERY } from "@/lib/engagement";
import { useLearnerGuard } from "@/lib/guards";
import { daysAgo, firstName, flaggedMisconception, resultMoment, SessionAnswer, thinkingLine, timeOfDay } from "@/lib/moments";
import { useConcepts } from "@/lib/useConcepts";

/**
 * One learning step. Practice: the explanation (with "Why this?") comes first and the question is
 * its micro-check. Placement (diagnostic) questions come first, so the explanation cannot give the
 * answer away; their explanation follows the answer.
 */
export default function SessionPage() {
  const ready = useLearnerGuard();
  const concepts = useConcepts();
  const { user } = useAuth();

  const [step, setStep] = useState<NextStepResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [advancing, setAdvancing] = useState(false);
  const [result, setResult] = useState<AttemptResult | null>(null);
  const [closeNotice, setCloseNotice] = useState<ChangeNoticeData | null>(null);
  const [lastAnswer, setLastAnswer] = useState<string | null>(null);
  const [answered, setAnswered] = useState(0);
  const [error, setError] = useState<string | null>(null);
  // ENGAGEMENT_UI only: this session's answers, the model's prediction for the current question
  // (fetched while the learner reads; the same endpoint the panel uses), the recap, the last visit
  const [answers, setAnswers] = useState<SessionAnswer[]>([]);
  const [insight, setInsight] = useState<ModelInsight | null>(null);
  const [showRecap, setShowRecap] = useState(false);
  const [lastVisit, setLastVisit] = useState<{ conceptId: string; when: string } | null>(null);
  const stepId = useRef<string | null>(null);

  const loadNext = useCallback(async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    setCloseNotice(null);
    setLastAnswer(null);
    setInsight(null);
    setShowRecap(false);
    try {
      const next = await api.session.next();
      stepId.current = next.recommendation.id;
      setStep(next);
      if (ENGAGEMENT_UI && next.item) {
        api.xai
          .model(next.recommendation.id)
          .then((i) => stepId.current === next.recommendation.id && setInsight(i))
          .catch(() => undefined); // only the "beat the prediction" moment needs it
      }
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

  useEffect(() => {
    if (!ready || !ENGAGEMENT_UI) return;
    api.learners
      .getHistory(10)
      .then((history) => {
        const last = history.find((h) => h.source === "attempt" && Object.keys(h.delta.mastery_changes).length);
        const when = last && daysAgo(last.created_at);
        if (last && when) setLastVisit({ conceptId: Object.keys(last.delta.mastery_changes)[0], when });
      })
      .catch(() => undefined);
  }, [ready]);

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
      const change = res.delta.mastery_changes[step.item.concept_id];
      setAnswers((a) => [...a, { conceptId: step.item!.concept_id, correct: res.correct, before: change?.[0] ?? null, after: change?.[1] ?? null }]);
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

  const next = useCallback(async () => {
    if (advancing) return;
    setAdvancing(true);
    if (step) {
      try {
        // closes the explanation's feedback (a no-op if the micro-check already did)
        const feedback = await api.explanations.close(step.explanation.id);
        if (feedback.change?.messages.length) setCloseNotice(feedback.change);
      } catch {
        // feedback is best effort; never block the learner on it
      }
    }
    if (ENGAGEMENT_UI && result && answers.length > 0 && answers.length % RECAP_EVERY === 0) {
      setStep(null);
      setResult(null);
      setShowRecap(true);
    } else {
      await loadNext();
    }
    setAdvancing(false);
  }, [advancing, step, result, answers.length, loadNext]);

  const canContinue = Boolean(step && !loading && (result || !step.item));

  // Enter continues once the answer is marked (unless a button, link or field has focus)
  useEffect(() => {
    if (!canContinue) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Enter" || e.repeat || e.defaultPrevented) return;
      const el = (e.target as HTMLElement | null)?.closest<HTMLElement>("button, a, input, textarea, select, summary, [role=tab], [contenteditable=true]");
      if (el && !(el instanceof HTMLButtonElement && el.disabled)) return; // let it do its own thing
      e.preventDefault();
      void next();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [canContinue, next]);

  if (!ready) return <PageLoading />;

  const placement = step?.recommendation.kind === "diagnostic_item";
  const concept = step ? concepts[step.recommendation.target_concept_id] : undefined;
  const explanationFirst = Boolean(step && !placement);
  const showExplanation = Boolean(step && (explanationFirst || result || !step.item));
  const name = firstName(user?.display_name);
  const names = Object.fromEntries(Object.entries(concepts).map(([id, c]) => [id, c.name]));
  const previous = answers.at(-1);
  const moment =
    ENGAGEMENT_UI && result
      ? resultMoment({
          correct: result.correct,
          pCorrect: insight?.recommendation_id === step?.recommendation.id ? (insight?.p_correct ?? null) : null,
          misconception: flaggedMisconception(result.delta.notes),
          turn: answers.length,
          example: explanationFirst ? "above" : "below",
        })
      : null;
  const masteryChange = result && step?.item ? result.delta.mastery_changes[step.item.concept_id] : undefined;

  const subtitle = !ENGAGEMENT_UI
    ? "One step at a time. Each step is chosen from what you know now."
    : answers.length === 0 && lastVisit
      ? `${timeOfDay(new Date().getHours())}${name ? `, ${name}` : ""}. Last time you worked on ${names[lastVisit.conceptId] ?? "a concept"}, ${lastVisit.when}.`
      : `${timeOfDay(new Date().getHours())}${name ? `, ${name}` : ""}. One step at a time, chosen from what you know now.`;

  return (
    <AppShell
      actions={
        canContinue ? (
          <motion.div
            className="w-full sm:w-auto"
            initial={ENGAGEMENT_UI ? { scale: 1 } : false}
            animate={ENGAGEMENT_UI ? { scale: [1, 1.04, 1] } : undefined}
            transition={{ duration: 0.5, delay: 0.6 }}
          >
            <Button size="lg" onClick={next} loading={advancing} className="w-full sm:w-auto" aria-keyshortcuts="Enter">
              Continue <span aria-hidden>→</span>
            </Button>
          </motion.div>
        ) : undefined
      }
    >
      <div className="mx-auto max-w-3xl space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-fg">Learn</h1>
            <p className="text-sm text-muted">{subtitle}</p>
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

        {ENGAGEMENT_UI && (answers.length > 0 || step?.item) && (
          <SessionStrip answers={answers} current={Boolean(step?.item && !result)} names={names} />
        )}

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
          {showRecap ? (
            <SessionRecap key="recap" answers={answers.slice(-RECAP_EVERY)} names={names} name={name} onContinue={loadNext} />
          ) : loading ? (
            <motion.div
              key="loading"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex flex-col items-center gap-3 rounded-xl border border-line bg-surface p-12 text-sm text-muted"
              aria-busy
              role="status"
            >
              {ENGAGEMENT_UI ? (
                <>
                  <span className="flex gap-1.5" aria-hidden>
                    {[0, 1, 2].map((i) => (
                      <motion.span
                        key={i}
                        className="h-1.5 w-1.5 rounded-full bg-primary"
                        animate={{ opacity: [0.25, 1, 0.25] }}
                        transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.2 }}
                      />
                    ))}
                  </span>
                  {thinkingLine({ name, lastConcept: previous ? names[previous.conceptId] : null, lastCorrect: previous?.correct })}
                </>
              ) : (
                <>
                  <Spinner className="text-primary" />
                  Choosing your next step…
                </>
              )}
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
                  correctAnswer={result?.correct_answer}
                />
              )}

              <div role="status" aria-live="polite">
                <AnimatePresence>
                  {result && (
                    <ResultMoment correct={result.correct} correctAnswer={result.correct_answer} moment={moment}>
                      {ENGAGEMENT_UI && masteryChange && step.item && (
                        <MasteryMeter concept={names[step.item.concept_id] ?? "this concept"} before={masteryChange[0]} after={masteryChange[1]} />
                      )}
                    </ResultMoment>
                  )}
                </AnimatePresence>
              </div>

              <ChangeNotice notice={result?.change} />

              {result && step.item && (
                <ModelInsightPanel
                  recommendationId={step.recommendation.id}
                  initial={insight?.recommendation_id === step.recommendation.id ? insight : null}
                  answeredCorrectly={result.correct}
                />
              )}

              {!explanationFirst && showExplanation && <ExplanationCard explanation={step.explanation} concept={concept} />}
            </motion.div>
          ) : null}
        </AnimatePresence>
      </div>
    </AppShell>
  );
}
