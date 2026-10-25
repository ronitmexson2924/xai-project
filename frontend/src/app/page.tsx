"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import React, { useEffect, useState } from "react";
import Navbar from "@/components/Navbar";
import { api, ApiException } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

interface Progress {
  questionnaireDone: boolean;
  pretestDone: boolean;
  posttestDone: boolean;
  answered: number;
}

export default function Home() {
  const { user, isLoading, withdraw } = useAuth();
  const router = useRouter();
  const [progress, setProgress] = useState<Progress | null>(null);
  const [confirmWithdraw, setConfirmWithdraw] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user?.consent_at) return;
    let alive = true;
    Promise.all([
      api.learners.getHistory(200),
      api.learners.getState(),
      api.tests.get("pretest").catch(() => null),
      api.tests.get("posttest").catch(() => null),
    ])
      .then(([history, state, pre, post]) => {
        if (!alive) return;
        setProgress({
          questionnaireDone: history.some((h) => h.source === "questionnaire"),
          pretestDone: Boolean(pre?.submitted),
          posttestDone: Boolean(post?.submitted),
          answered: state.total_attempts,
        });
      })
      .catch(() => alive && setProgress(null));
    return () => {
      alive = false;
    };
  }, [user]);

  const handleWithdraw = async () => {
    if (!confirmWithdraw) {
      setConfirmWithdraw(true);
      return;
    }
    try {
      await withdraw();
      router.push("/login");
    } catch (err) {
      setError(err instanceof ApiException ? err.message : "Could not withdraw. Please try again.");
    }
  };

  const steps = progress
    ? [
        { label: "Consent", done: true, href: "/consent" },
        { label: "Starting questionnaire", done: progress.questionnaireDone, href: "/onboarding" },
        { label: "Pre-test", done: progress.pretestDone, href: "/tests/pretest" },
        { label: `Learn (${progress.answered} answered)`, done: false, href: "/session" },
        { label: "Post-test (at the end of the study)", done: progress.posttestDone, href: "/tests/posttest" },
      ]
    : [];
  const nextStep = steps.find((s) => !s.done);

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100">
      <Navbar />
      <main className="flex-1 max-w-3xl w-full mx-auto px-4 sm:px-6 py-10 space-y-8">
        <section className="space-y-3">
          <h1 className="text-3xl font-bold text-white">Learn data structures and algorithms, one step at a time</h1>
          <p className="text-sm text-slate-400 leading-relaxed">
            The app picks your next question from a map of 63 DSA concepts, explains each concept in a
            style it adjusts to your feedback, and always tells you why it chose what it did.
          </p>
        </section>

        {isLoading ? (
          <p className="text-sm text-slate-500">Loading…</p>
        ) : !user ? (
          <div className="flex gap-3">
            <Link href="/login" className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-sm font-semibold text-white">
              Log in or create an account
            </Link>
          </div>
        ) : !user.consent_at ? (
          <Link href="/consent" className="inline-block px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-sm font-semibold text-white">
            Read the study information to start
          </Link>
        ) : (
          <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 space-y-4" data-testid="study-steps">
            <h2 className="text-base font-semibold text-white">Your study path</h2>
            <ol className="space-y-2">
              {steps.map((s) => (
                <li key={s.label} className="flex items-center justify-between text-sm">
                  <span className={s.done ? "text-slate-500 line-through" : "text-slate-200"}>{s.label}</span>
                  {s.done ? (
                    <span className="text-xs text-emerald-400">done</span>
                  ) : (
                    <Link href={s.href} className="text-xs text-indigo-400 hover:text-indigo-300">
                      open →
                    </Link>
                  )}
                </li>
              ))}
            </ol>
            {nextStep && (
              <Link
                href={nextStep.href}
                className="inline-block px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-sm font-semibold text-white"
              >
                Continue: {nextStep.label}
              </Link>
            )}
          </section>
        )}

        {user && (
          <section className="rounded-2xl border border-rose-500/20 bg-rose-950/10 p-5 space-y-2">
            <h2 className="text-sm font-semibold text-rose-200">Withdraw from the study</h2>
            <p className="text-xs text-slate-400">
              Your account stops working immediately and all your data is deleted by the next clean-up run.
              This cannot be undone.
            </p>
            {error && <p className="text-xs text-rose-300">{error}</p>}
            <button
              type="button"
              onClick={handleWithdraw}
              className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-rose-600/80 hover:bg-rose-600 text-white"
            >
              {confirmWithdraw ? "Yes, withdraw and delete my data" : "Withdraw"}
            </button>
            {confirmWithdraw && (
              <button type="button" onClick={() => setConfirmWithdraw(false)} className="ml-2 text-xs text-slate-400">
                Cancel
              </button>
            )}
          </section>
        )}
      </main>
    </div>
  );
}
