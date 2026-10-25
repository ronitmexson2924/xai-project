"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import React, { useCallback, useEffect, useState } from "react";
import { ApiException, useAuth } from "@/lib/auth-context";
import {
  AttemptResult,
  ChangeNotice,
  Concept,
  NextStepResponse,
  PublicItem,
  api,
} from "@/lib/api";
import { useExplanationTelemetry } from "@/lib/useExplanationTelemetry";
import { ItemCard } from "@/components/ItemCard";
import { ExplanationCard } from "@/components/ExplanationCard";
import { WhyPanel } from "@/components/WhyPanel";

// One step (tasks/mit.md M4): answer the item -> see the result and the explanation with
// "Why this?" -> micro-check (or continue) -> next. Answers are tied to what was served, so the
// server can refuse replays and items that were never shown.
type Phase = "answer" | "learn" | "check" | "done";

export default function SessionPage() {
  const router = useRouter();
  const { user, isLoading: authLoading } = useAuth();

  const [step, setStep] = useState<NextStepResponse | null>(null);
  const [phase, setPhase] = useState<Phase>("answer");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<AttemptResult | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [check, setCheck] = useState<PublicItem | null>(null);
  const [checkResult, setCheckResult] = useState<AttemptResult | null>(null);
  const [checkSelected, setCheckSelected] = useState<string | null>(null);
  const [concepts, setConcepts] = useState<Record<string, Concept>>({});
  const [count, setCount] = useState(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const telemetry = useExplanationTelemetry(phase === "answer" ? null : step?.explanation.id);

  useEffect(() => {
    if (authLoading) return;
    if (!user) router.push("/login");
    else if (!user.consent_at) router.push("/consent");
    else if (!user.questionnaire_done) router.push("/onboarding");
  }, [user, authLoading, router]);

  useEffect(() => {
    if (!user?.consent_at) return;
    api.graph
      .get()
      .then((g) => setConcepts(Object.fromEntries(g.concepts.map((c) => [c.id, c]))))
      .catch(() => undefined); // the names are a nicety; the session works without them
  }, [user]);

  const showError = (err: unknown, fallback: string) => {
    if (err instanceof ApiException) {
      if (err.code === "QUESTIONNAIRE_REQUIRED") {
        router.push("/onboarding");
        return;
      }
      setErrorMsg(err.message);
    } else {
      setErrorMsg(fallback);
    }
  };

  const loadNext = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    setResult(null);
    setSelected(null);
    setCheck(null);
    setCheckResult(null);
    setCheckSelected(null);
    try {
      const next = await api.session.next();
      setStep(next);
      setPhase(next.item ? "answer" : "learn");
    } catch (err) {
      showError(err, "Could not load the next step. Please retry.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (user?.consent_at && user.questionnaire_done) {
      const t = setTimeout(() => void loadNext(), 0);
      return () => clearTimeout(t);
    }
  }, [user, loadNext]);

  const submitAnswer = async (response: string, latencyMs: number) => {
    if (!step?.item || busy) return;
    setBusy(true);
    setErrorMsg(null);
    setSelected(response);
    try {
      const r = await api.attempts.submit({
        item_id: step.item.id,
        response,
        latency_ms: latencyMs,
        hints_used: 0,
        recommendation_id: step.recommendation.id,
      });
      setResult(r);
      setCount((c) => c + 1);
      setPhase("learn");
    } catch (err) {
      showError(err, "Could not submit your answer. Please retry.");
    } finally {
      setBusy(false);
    }
  };

  const startCheck = async () => {
    const id = step?.explanation.followup_item_id;
    if (!id) return;
    setBusy(true);
    try {
      setCheck(await api.items.get(id));
      setPhase("check");
    } catch (err) {
      showError(err, "Could not load the check question.");
    } finally {
      setBusy(false);
    }
  };

  const submitCheck = async (response: string, latencyMs: number) => {
    if (!step || !check || busy) return;
    setBusy(true);
    setCheckSelected(response);
    try {
      await telemetry.flush(); // the server summarises the reading when the check comes in
      const r = await api.attempts.submit({
        item_id: check.id,
        response,
        latency_ms: latencyMs,
        hints_used: 0,
        explanation_id: step.explanation.id,
      });
      setCheckResult(r);
      setPhase("done");
    } catch (err) {
      showError(err, "Could not submit your answer. Please retry.");
    } finally {
      setBusy(false);
    }
  };

  const finishWithoutCheck = async () => {
    if (!step) return;
    setBusy(true);
    try {
      telemetry.trackDismissed();
      await telemetry.flush();
      await api.explanations.close(step.explanation.id);
      await loadNext();
    } catch (err) {
      showError(err, "Could not save your progress. Please retry.");
    } finally {
      setBusy(false);
    }
  };

  if (authLoading) {
    return <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-400">Loading…</div>;
  }

  const concept = step ? concepts[step.recommendation.target_concept_id] ?? null : null;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="sticky top-0 z-10 border-b border-slate-800 bg-slate-950/90 backdrop-blur">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3">
          <Link href="/" className="text-sm text-slate-400 hover:text-white">← Home</Link>
          <span className="text-xs text-slate-400">
            Answered this session: <strong className="text-indigo-300">{count}</strong>
          </span>
        </div>
      </header>

      <main className="mx-auto max-w-3xl space-y-6 px-4 py-8">
        {errorMsg && (
          <div role="alert" className="flex items-center justify-between rounded-xl border border-rose-500/30 bg-rose-950/30 p-3 text-sm text-rose-200">
            <span>{errorMsg}</span>
            <button type="button" onClick={() => void loadNext()} className="rounded-lg px-3 py-1 hover:bg-rose-500/10">
              Retry
            </button>
          </div>
        )}

        {loading && <p className="text-center text-sm text-slate-400">Choosing your next step…</p>}

        {!loading && step && (
          <>
            {concept && (
              <h1 className="text-lg font-semibold text-white">{concept.name}</h1>
            )}

            {step.item && (
              <ItemCard
                item={step.item}
                onAnswer={submitAnswer}
                isSubmitting={busy && phase === "answer"}
                disabled={phase !== "answer"}
                selectedAnswer={selected}
                isCorrect={result?.correct}
              />
            )}

            {result && <ResultBanner result={result} />}

            {phase !== "answer" && (
              <div className="space-y-4">
                <ExplanationCard explanation={step.explanation} telemetry={telemetry} concept={concept} />
                <WhyPanel recommendationId={step.recommendation.id} telemetry={telemetry} />
              </div>
            )}

            {phase === "learn" && (
              <div className="flex flex-col gap-3 sm:flex-row sm:justify-end">
                {step.explanation.followup_item_id ? (
                  <button type="button" disabled={busy} onClick={() => void startCheck()}
                    className="rounded-xl bg-indigo-600 px-6 py-3 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50">
                    Check my understanding →
                  </button>
                ) : (
                  <button type="button" disabled={busy} onClick={() => void finishWithoutCheck()}
                    className="rounded-xl bg-indigo-600 px-6 py-3 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50">
                    Continue →
                  </button>
                )}
              </div>
            )}

            {(phase === "check" || phase === "done") && check && (
              <ItemCard
                item={check}
                onAnswer={submitCheck}
                isSubmitting={busy && phase === "check"}
                disabled={phase === "done"}
                selectedAnswer={checkSelected}
                isCorrect={checkResult?.correct}
              />
            )}

            {phase === "done" && checkResult && (
              <>
                <ResultBanner result={checkResult} />
                <div className="flex justify-end">
                  <button type="button" disabled={busy} onClick={() => void loadNext()}
                    className="rounded-xl bg-indigo-600 px-6 py-3 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50">
                    Next step →
                  </button>
                </div>
              </>
            )}
          </>
        )}
      </main>
    </div>
  );
}

function ResultBanner({ result }: { result: AttemptResult }) {
  const notices: ChangeNotice[] = [result.change, result.feedback_change].filter(
    (n): n is ChangeNotice => Boolean(n)
  );
  const messages = notices.flatMap((n) => n.messages ?? []);
  return (
    <div
      role="status"
      className={`rounded-2xl border p-4 text-sm ${
        result.correct
          ? "border-emerald-500/30 bg-emerald-950/30 text-emerald-100"
          : "border-rose-500/30 bg-rose-950/30 text-rose-100"
      }`}
    >
      <p className="font-semibold">{result.correct ? "Correct." : "Not quite."}</p>
      {!result.correct && result.correct_answer && (
        <p className="mt-1 text-xs">The answer is: {result.correct_answer}</p>
      )}
      {messages.length > 0 && (
        <ul className="mt-2 list-disc space-y-0.5 pl-5 text-xs text-slate-300">
          {messages.map((m, i) => (
            <li key={i}>{m}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
