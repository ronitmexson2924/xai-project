"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import React, { useEffect, useState } from "react";
import { ApiException, useAuth } from "@/lib/auth-context";
import { QuestionnaireItem, api } from "@/lib/api";

const LIKERT_OPTIONS = [
  { value: 1, label: "Strongly Disagree", short: "1" },
  { value: 2, label: "Disagree", short: "2" },
  { value: 3, label: "Neutral", short: "3" },
  { value: 4, label: "Agree", short: "4" },
  { value: 5, label: "Strongly Agree", short: "5" },
];

export default function OnboardingPage() {
  const router = useRouter();
  const { user, isLoading: authLoading, refreshUser } = useAuth();

  const [items, setItems] = useState<QuestionnaireItem[]>([]);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loadingItems, setLoadingItems] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [step, setStep] = useState<"questionnaire" | "diagnostic_intro">("questionnaire");
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

  // Load questionnaire items
  useEffect(() => {
    if (!user || !user.consent_at) return;

    let mounted = true;
    api.onboarding
      .getQuestionnaire()
      .then((data) => {
        if (mounted) {
          setItems(data);
          setLoadingItems(false);
        }
      })
      .catch((err) => {
        if (mounted) {
          setErrorMsg(err instanceof ApiException ? err.message : "Failed to load questionnaire.");
          setLoadingItems(false);
        }
      });

    return () => {
      mounted = false;
    };
  }, [user]);

  // Keyboard navigation for Likert 1-5
  useEffect(() => {
    if (step !== "questionnaire" || items.length === 0) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (["1", "2", "3", "4", "5"].includes(e.key)) {
        const val = parseInt(e.key, 10);
        const currentItem = items[currentIndex];
        if (currentItem) {
          e.preventDefault();
          setAnswers((prev) => ({ ...prev, [currentItem.id]: val }));
        }
      } else if (e.key === "Enter") {
        const currentItem = items[currentIndex];
        if (answers[currentItem.id]) {
          e.preventDefault();
          if (currentIndex < items.length - 1) {
            setCurrentIndex((i) => i + 1);
          }
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [step, items, currentIndex, answers]);

  const handleSelectOption = (itemId: string, value: number) => {
    setAnswers((prev) => ({ ...prev, [itemId]: value }));
  };

  const handleNext = () => {
    if (currentIndex < items.length - 1) {
      setCurrentIndex((i) => i + 1);
    }
  };

  const handlePrev = () => {
    if (currentIndex > 0) {
      setCurrentIndex((i) => i - 1);
    }
  };

  const handleSubmitQuestionnaire = async () => {
    setErrorMsg(null);
    setSubmitting(true);
    try {
      await api.onboarding.submitQuestionnaire(answers);
      await refreshUser(); // questionnaire_done is now true, which the session page checks
      setStep("diagnostic_intro");
    } catch (err) {
      if (err instanceof ApiException) {
        setErrorMsg(`[${err.code}] ${err.message}`);
      } else {
        setErrorMsg("Failed to submit questionnaire. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (authLoading || loadingItems) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-400 text-sm">
        <div className="flex items-center gap-3">
          <span className="w-3 h-3 rounded-full bg-indigo-500 animate-ping" />
          Loading onboarding assessment...
        </div>
      </div>
    );
  }

  // Diagnostic Intro View
  if (step === "diagnostic_intro" || user?.questionnaire_done) {  // it is taken once
    return (
      <div className="flex min-h-screen flex-col items-center justify-center p-4 sm:p-8 bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-slate-100">
        <div className="w-full max-w-xl space-y-6">
          <div className="rounded-3xl border border-slate-800 bg-slate-900/90 p-6 sm:p-10 shadow-2xl backdrop-blur-xl space-y-6 text-center">
            <div className="w-16 h-16 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center text-3xl mx-auto shadow-lg shadow-emerald-500/10">
              ✓
            </div>

            <div className="space-y-2">
              <span className="text-xs font-mono uppercase tracking-widest text-emerald-400">
                Questionnaire Complete
              </span>
              <h1 className="text-2xl sm:text-3xl font-extrabold text-white">
                Next: a short starting quiz
              </h1>
              <p className="text-sm text-slate-300 leading-relaxed max-w-md mx-auto">
                Your answers are saved. A short quiz shows where you are starting from; then
                practice begins with a few questions across the course to find your level.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 text-left space-y-2 text-xs text-slate-400">
              <div className="font-semibold text-slate-200">How this works:</div>
              <ul className="list-disc pl-4 space-y-1">
                <li>The starting quiz has 15 questions and gives no feedback.</li>
                <li>Wrong answers have no penalty: they only tell the system where to begin.</li>
                <li>In practice, each question is followed by an explanation and a quick check.</li>
              </ul>
            </div>

            <div className="pt-2">
              <Link
                href="/pretest"
                className="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-3 px-6 shadow-lg shadow-indigo-600/30 transition-all text-sm"
              >
                Start the quiz →
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Questionnaire Assessment View
  const currentItem = items[currentIndex];
  const totalCount = items.length;
  const answeredCount = Object.keys(answers).length;
  const isAllAnswered = totalCount > 0 && answeredCount === totalCount;
  const currentAnswer = currentItem ? answers[currentItem.id] : undefined;

  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-4 sm:p-8 bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-slate-100">
      <div className="w-full max-w-2xl space-y-6">
        {/* Header and Progress */}
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <div className="text-xs font-mono uppercase tracking-wider text-indigo-400">
              Step 2 of 2: Intake Assessment
            </div>
            <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
              Learning Preference Questionnaire
            </h1>
          </div>
          <div className="text-right">
            <span className="text-xs font-mono text-slate-400">
              Question {currentIndex + 1} of {totalCount}
            </span>
            <div className="w-28 h-2 rounded-full bg-slate-800 overflow-hidden mt-1.5">
              <div
                className="h-full bg-indigo-500 transition-all duration-300"
                style={{ width: `${(answeredCount / totalCount) * 100}%` }}
              />
            </div>
          </div>
        </div>

        {errorMsg && (
          <div className="rounded-xl bg-rose-500/10 border border-rose-500/30 p-3 text-xs text-rose-300">
            {errorMsg}
          </div>
        )}

        {/* Current Question Card */}
        {currentItem && (
          <div className="rounded-3xl border border-slate-800 bg-slate-900/90 p-6 sm:p-8 shadow-2xl backdrop-blur-xl space-y-6">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                  How much do you agree?
                </span>
                <span className="text-[11px] text-slate-500 hidden sm:inline">
                  (Press <kbd className="px-1 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">1-5</kbd> to select)
                </span>
              </div>
              <p className="text-base sm:text-lg font-medium text-slate-100 leading-relaxed">
                &ldquo;{currentItem.text}&rdquo;
              </p>
            </div>

            {/* 1-5 Likert Options */}
            <div className="space-y-2.5" role="radiogroup" aria-label="Likert scale">
              {LIKERT_OPTIONS.map((opt) => {
                const isSelected = currentAnswer === opt.value;
                return (
                  <button
                    key={opt.value}
                    type="button"
                    role="radio"
                    aria-checked={isSelected}
                    onClick={() => handleSelectOption(currentItem.id, opt.value)}
                    className={`w-full text-left p-3.5 rounded-xl border transition-all flex items-center justify-between ${
                      isSelected
                        ? "border-indigo-500 bg-indigo-500/15 text-white ring-1 ring-indigo-500 shadow-md shadow-indigo-500/10"
                        : "border-slate-800 bg-slate-950/50 hover:border-slate-700 hover:bg-slate-950/80 text-slate-300"
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className={`w-6 h-6 rounded-lg border flex items-center justify-center font-mono text-xs font-semibold ${
                          isSelected
                            ? "bg-indigo-600 text-white border-indigo-500"
                            : "bg-slate-800 text-slate-400 border-slate-700"
                        }`}
                      >
                        {opt.short}
                      </div>
                      <span className="text-sm font-medium">{opt.label}</span>
                    </div>
                    {isSelected && (
                      <span className="text-indigo-400 text-xs font-semibold">Selected ✓</span>
                    )}
                  </button>
                );
              })}
            </div>

            {/* Navigation and Submission Buttons */}
            <div className="flex items-center justify-between pt-4 border-t border-slate-800">
              <button
                type="button"
                disabled={currentIndex === 0}
                onClick={handlePrev}
                className={`px-4 py-2 rounded-xl text-xs font-medium transition-colors ${
                  currentIndex > 0
                    ? "text-slate-300 hover:text-white bg-slate-800/80 hover:bg-slate-800 border border-slate-700"
                    : "text-slate-600 bg-transparent cursor-not-allowed"
                }`}
              >
                ← Previous
              </button>

              <div className="flex items-center gap-3">
                {currentIndex < totalCount - 1 ? (
                  <button
                    type="button"
                    disabled={!currentAnswer}
                    onClick={handleNext}
                    className={`px-5 py-2.5 rounded-xl text-xs font-semibold transition-all ${
                      currentAnswer
                        ? "bg-indigo-600 hover:bg-indigo-500 text-white shadow-md shadow-indigo-600/20"
                        : "bg-slate-800 text-slate-500 cursor-not-allowed"
                    }`}
                  >
                    Next Question →
                  </button>
                ) : (
                  <button
                    type="button"
                    disabled={!isAllAnswered || submitting}
                    onClick={handleSubmitQuestionnaire}
                    className={`px-6 py-2.5 rounded-xl text-xs font-bold transition-all ${
                      isAllAnswered && !submitting
                        ? "bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-600/30"
                        : "bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700/50"
                    }`}
                  >
                    {submitting ? "Calculating profile..." : "Complete & Begin Diagnostic"}
                  </button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
