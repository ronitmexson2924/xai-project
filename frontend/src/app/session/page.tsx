"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import React, { useCallback, useEffect, useState } from "react";
import { ApiException, useAuth } from "@/lib/auth-context";
import {
  AttemptResult,
  NextStepResponse,
  api,
} from "@/lib/api";
import { ItemCard } from "@/components/ItemCard";
import { ReasonsPanel } from "@/components/ReasonsPanel";
import { ExplanationCard } from "@/components/ExplanationCard";

export default function SessionPage() {
  const router = useRouter();
  const { user, isLoading: authLoading } = useAuth();

  const [stepData, setStepData] = useState<NextStepResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [submittingAttempt, setSubmittingAttempt] = useState(false);
  const [attemptResult, setAttemptResult] = useState<AttemptResult | null>(null);
  const [lastSelectedAnswer, setLastSelectedAnswer] = useState<string | null>(null);
  const [sessionItemCount, setSessionItemCount] = useState<number>(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Authentication & Consent checks
  useEffect(() => {
    if (!authLoading) {
      if (!user) {
        router.push("/login");
      } else if (!user.consent_at) {
        router.push("/consent");
      }
    }
  }, [user, authLoading, router]);

  const fetchNextRecommendation = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    setAttemptResult(null);
    setLastSelectedAnswer(null);

    try {
      const nextStep = await api.session.next();
      setStepData(nextStep);
    } catch (err) {
      if (err instanceof ApiException) {
        setErrorMsg(`[${err.code}] ${err.message}`);
      } else {
        setErrorMsg("Failed to retrieve next recommendation. Please retry.");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch initial recommendation on mount
  useEffect(() => {
    if (user && user.consent_at) {
      const timer = setTimeout(() => {
        fetchNextRecommendation();
      }, 0);
      return () => clearTimeout(timer);
    }
  }, [user, fetchNextRecommendation]);

  const handleAnswerSubmit = async (response: string, latencyMs: number) => {
    if (!stepData?.item) return;

    setSubmittingAttempt(true);
    setErrorMsg(null);
    setLastSelectedAnswer(response);

    try {
      const result = await api.attempts.submit({
        item_id: stepData.item.id,
        response,
        latency_ms: latencyMs,
        hints_used: 0,
        explanation_id: stepData.explanation.id,
      });

      setAttemptResult(result);
      setSessionItemCount((c) => c + 1);
    } catch (err) {
      if (err instanceof ApiException) {
        setErrorMsg(`[${err.code}] ${err.message}`);
      } else {
        setErrorMsg("Failed to submit attempt. Please retry.");
      }
    } finally {
      setSubmittingAttempt(false);
    }
  };

  if (authLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-400 text-sm">
        Authenticating...
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100">
      {/* Session Top Bar */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="text-xs text-slate-400 hover:text-white transition-colors flex items-center gap-1.5"
            >
              <span>←</span>
              <span className="hidden sm:inline">Dashboard</span>
            </Link>
            <span className="text-slate-700">|</span>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400" />
              <span className="text-xs font-semibold text-white">Active Session</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="text-xs font-mono px-2.5 py-1 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
              Completed in Session: <strong className="text-indigo-400">{sessionItemCount}</strong>
            </div>
            {user && (
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 hidden sm:inline">
                Arm: {user.arm}
              </span>
            )}
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-4xl w-full mx-auto px-4 sm:px-6 py-6 sm:py-8 space-y-6">
        {/* Error Alert */}
        {errorMsg && (
          <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-xs text-rose-300 flex items-center justify-between">
            <span>{errorMsg}</span>
            <button
              type="button"
              onClick={fetchNextRecommendation}
              className="px-3 py-1 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 font-medium"
            >
              Retry
            </button>
          </div>
        )}

        {/* Milestone Indicator */}
        {sessionItemCount >= 3 && !attemptResult && (
          <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-4 flex items-center justify-between text-xs text-emerald-300 animate-in fade-in duration-300">
            <div className="flex items-center gap-2">
              <span className="text-base">🎉</span>
              <span>
                <strong>Milestone Reached:</strong> You have completed {sessionItemCount} items! Your
                BKT model and psychometrics are actively closing the feedback loop.
              </span>
            </div>
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="rounded-3xl border border-slate-800 bg-slate-900/50 p-12 text-center space-y-4">
            <div className="w-8 h-8 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin mx-auto" />
            <div className="space-y-1">
              <div className="text-sm font-semibold text-white">Re-planning next concept...</div>
              <p className="text-xs text-slate-400">
                Running Thompson sampling & grounded explanation generation
              </p>
            </div>
          </div>
        )}

        {/* Active Learning Item & Feedback Flow */}
        {!loading && stepData && (
          <div className="space-y-6">
            {/* Step 1: Question Item Card */}
            {stepData.item && (
              <ItemCard
                item={stepData.item}
                onAnswer={handleAnswerSubmit}
                isSubmitting={submittingAttempt}
                disabled={attemptResult !== null}
                selectedAnswer={lastSelectedAnswer}
                isCorrect={attemptResult?.correct}
              />
            )}

            {/* Step 2: Attempt Feedback Banner */}
            {attemptResult && (
              <div
                className={`rounded-2xl border p-5 shadow-xl transition-all animate-in fade-in slide-in-from-top-2 duration-300 ${
                  attemptResult.correct
                    ? "border-emerald-500/30 bg-emerald-950/30 text-emerald-100"
                    : "border-rose-500/30 bg-rose-950/30 text-rose-100"
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-9 h-9 rounded-xl flex items-center justify-center text-lg font-bold ${
                        attemptResult.correct
                          ? "bg-emerald-500/20 text-emerald-300"
                          : "bg-rose-500/20 text-rose-300"
                      }`}
                    >
                      {attemptResult.correct ? "✓" : "✗"}
                    </div>
                    <div>
                      <h4 className="text-sm font-bold">
                        {attemptResult.correct ? "Correct! Well done." : "Not quite right."}
                      </h4>
                      <p className="text-xs text-slate-300 mt-0.5">
                        {attemptResult.correct
                          ? "Your understanding of the invariant holds."
                          : (attemptResult.correct_answer
                              ? `Expected answer: ${attemptResult.correct_answer}.`
                              : "Review the grounded explanation below to see the trace.")}
                      </p>
                    </div>
                  </div>

                  {attemptResult.delta?.notes && attemptResult.delta.notes.length > 0 && (
                    <span className="text-[11px] font-mono px-2.5 py-1 rounded-md bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                      {attemptResult.delta.notes[0]}
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* Step 3: Explanation Card + Reasons Panel */}
            {/* Show explanation during feedback phase, or immediately if recommendation has no item */}
            {(attemptResult !== null || !stepData.item) && (
              <div className="space-y-6 animate-in fade-in duration-300">
                {/* Pedagogical "Why this?" panel */}
                <ReasonsPanel
                  reasons={stepData.recommendation.reasons}
                  targetConceptId={stepData.recommendation.target_concept_id}
                />

                {/* Grounded Explanation with visible dwell & telemetry tracking */}
                <ExplanationCard
                  explanation={stepData.explanation}
                  showTelemetryDebug={false}
                />

                {/* Step 4: Continue CTA Button */}
                <div className="pt-2 flex items-center justify-between">
                  <div className="text-xs text-slate-400">
                    Interacting with the explanation updates your trait and mastery models.
                  </div>
                  <button
                    type="button"
                    onClick={fetchNextRecommendation}
                    className="px-6 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-sm shadow-lg shadow-indigo-600/30 transition-all flex items-center gap-2"
                  >
                    <span>Continue to Next Concept</span>
                    <span>→</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
