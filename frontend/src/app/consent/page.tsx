"use client";

import { useRouter } from "next/navigation";
import React, { useState } from "react";
import { ApiException, useAuth } from "@/lib/auth-context";

export default function ConsentPage() {
  const router = useRouter();
  const { user, giveConsent, isLoading } = useAuth();
  const [consenting, setConsenting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // If not authenticated, redirect to login
  React.useEffect(() => {
    if (!isLoading && !user) {
      router.push("/login");
    }
  }, [user, isLoading, router]);

  const handleConsent = async () => {
    setErrorMsg(null);
    setConsenting(true);
    try {
      await giveConsent();
      router.push("/onboarding");
    } catch (err) {
      if (err instanceof ApiException) {
        setErrorMsg(`[${err.code}] ${err.message}`);
      } else {
        setErrorMsg("Failed to record consent. Please check your connection.");
      }
    } finally {
      setConsenting(false);
    }
  };

  if (isLoading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-400 text-sm">
        Loading learner profile...
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-4 sm:p-8 bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950">
      <div className="w-full max-w-2xl space-y-6">
        <div className="text-center space-y-2">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            Study Protocol & Privacy Consent
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-white">
            Informed Research Consent
          </h1>
          <p className="text-sm text-slate-400">
            Participant: <span className="text-white font-medium">{user.display_name}</span> ({user.email})
          </p>
        </div>

        <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6 sm:p-8 shadow-2xl backdrop-blur-xl space-y-6">
          {errorMsg && (
            <div className="rounded-lg bg-rose-500/10 border border-rose-500/30 p-3 text-xs text-rose-300">
              {errorMsg}
            </div>
          )}

          <div className="space-y-4 text-sm text-slate-300 leading-relaxed">
            <h3 className="text-base font-semibold text-white">About This Research</h3>
            <p>
              You are participating in a study evaluating the{" "}
              <strong className="text-indigo-300">
                Psychometric Concept-Graph Explanation-Feedback Engine
              </strong>
              . This platform dynamically tailors Data Structures & Algorithms
              (DSA) pedagogical explanations to optimize understanding and concept mastery.
            </p>

            <p>
              Participants are placed at random in one of several versions of the app, which differ in
              how explanations are adapted. You will not be told which version you use until the study
              ends, so that the comparison stays fair.
            </p>
            <h3 className="text-base font-semibold text-white pt-2">Data Collection & Telemetry</h3>
            <ul className="list-disc pl-5 space-y-1.5 text-slate-400">
              <li>
                <strong className="text-slate-200">Active Reading Dwell Time:</strong> Logged
                strictly when the explanation card is visible in the viewport.
              </li>
              <li>
                <strong className="text-slate-200">Interactive Telemetry:</strong> Card
                expansion, replay actions, and optional clarity ratings.
              </li>
              <li>
                <strong className="text-slate-200">Your answers:</strong> to practice questions and to a
                short test at the start and at the end.
              </li>
              <li>
                <strong className="text-slate-200">A starting questionnaire</strong> about how you like
                explanations and how you approach problems. The app turns it into estimates that you can
                see, with the reasons, on your progress page.
              </li>
            </ul>

            <h3 className="text-base font-semibold text-white pt-2">Privacy & Participant Rights</h3>
            <ul className="list-disc pl-5 space-y-1.5 text-slate-400">
              <li>Research exports use pseudonymous identifiers, never your name or email.</li>
              <li>No third-party analytics or external trackers are loaded.</li>
              <li>
                Taking part is voluntary. You can withdraw at any time from the home page; your account
                stops working immediately and your data is deleted.
              </li>
            </ul>
          </div>

          <div className="pt-4 border-t border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-4">
            {user.consent_at ? (
              <div className="w-full flex items-center justify-between">
                <div className="text-xs text-emerald-400 flex items-center gap-1.5 font-medium">
                  ✓ Consent recorded on {new Date(user.consent_at).toLocaleDateString()}
                </div>
                <button
                  type="button"
                  onClick={() => router.push("/")}
                  className="rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-indigo-500 transition-colors shadow-lg"
                >
                  Continue to Learning
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={handleConsent}
                disabled={consenting}
                className="w-full rounded-lg bg-emerald-600 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-emerald-600/30 hover:bg-emerald-500 hover:shadow-emerald-500/50 transition-all disabled:opacity-50 disabled:cursor-not-allowed text-center"
              >
                {consenting ? "Recording Consent..." : "I Understand & Give Research Consent"}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
