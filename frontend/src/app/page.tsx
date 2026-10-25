"use client";

import Link from "next/link";
import React, { useState } from "react";
import { useAuth } from "@/lib/auth-context";

export default function Home() {
  const { user, logout, isLoading } = useAuth();
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const handleDeleteAccount = async () => {
    if (!deleteConfirm) {
      setDeleteConfirm(true);
      return;
    }
    setDeleting(true);
    try {
      const token = localStorage.getItem("pcg_token");
      await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/me`,
        {
          method: "DELETE",
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        }
      );
      logout();
    } finally {
      setDeleting(false);
      setDeleteConfirm(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100">
      {/* Top Navbar */}
      <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center font-bold text-white shadow-md shadow-indigo-500/30">
              Ψ
            </div>
            <div>
              <span className="font-semibold text-white tracking-tight">PCG Engine</span>
              <span className="hidden sm:inline-block ml-2 text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                DSA Adaptive Learning
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {isLoading ? (
              <span className="text-xs text-slate-500">Checking auth...</span>
            ) : user ? (
              <div className="flex items-center gap-3">
                <span className="text-xs text-slate-300 hidden md:inline">
                  {user.display_name}
                </span>
                <span className="text-xs font-mono px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                  {user.arm}
                </span>
                <button
                  type="button"
                  onClick={logout}
                  className="text-xs text-slate-400 hover:text-white px-2.5 py-1 rounded-md border border-slate-800 hover:border-slate-700 transition-colors"
                >
                  Sign Out
                </button>
              </div>
            ) : (
              <Link
                href="/login"
                className="text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white px-3.5 py-1.5 rounded-lg shadow-md transition-colors"
              >
                Sign In / Register
              </Link>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 py-8 space-y-8">
        {/* Hero Section */}
        <div className="rounded-3xl border border-slate-800 bg-gradient-to-br from-slate-900 via-slate-900/90 to-indigo-950/40 p-6 sm:p-10 shadow-2xl relative overflow-hidden">
          <div className="absolute top-0 right-0 -mr-16 -mt-16 w-64 h-64 rounded-full bg-indigo-500/10 blur-3xl pointer-events-none" />

          <div className="max-w-2xl space-y-4 relative z-10">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
              Adaptive DSA Explanation & Feedback Engine
            </div>
            <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight leading-tight">
              Personalized Algorithm Explanations Tuned to How You Learn
            </h1>
            <p className="text-sm sm:text-base text-slate-300 leading-relaxed">
              Every learner processes abstraction, formal rules, and worked examples
              differently. PCG combines Bayesian Knowledge Tracing with psychometric trait
              inference to continuously close the feedback loop.
            </p>

            <div className="pt-2 flex flex-wrap gap-3">
              {!user ? (
                <Link
                  href="/login"
                  className="rounded-xl bg-indigo-600 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-600/30 hover:bg-indigo-500 transition-all"
                >
                  Join Research Study →
                </Link>
              ) : !user.consent_at ? (
                <Link
                  href="/consent"
                  className="rounded-xl bg-amber-600 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-amber-600/30 hover:bg-amber-500 transition-all animate-pulse"
                >
                  Complete Informed Consent →
                </Link>
              ) : (
                <div className="flex flex-wrap items-center gap-3">
                  <Link
                    href="/session"
                    className="rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white px-5 py-3 text-sm font-semibold shadow-lg shadow-indigo-600/30 transition-all flex items-center gap-2"
                  >
                    <span>Launch Learning Session</span>
                    <span>→</span>
                  </Link>
                  <Link
                    href="/onboarding"
                    className="rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 px-4 py-3 text-sm font-medium border border-slate-700 transition-all"
                  >
                    Intake Assessment
                  </Link>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* User Status Card */}
        {user && (
          <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-white">Learner Account Status</h2>
              <span
                className={`text-xs px-2.5 py-0.5 rounded-full font-medium ${
                  user.consent_at
                    ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                    : "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                }`}
              >
                {user.consent_at ? "Consent Active" : "Consent Pending"}
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
              <div className="p-3.5 rounded-xl bg-slate-950/50 border border-slate-800">
                <span className="text-xs text-slate-400 block mb-1">Participant</span>
                <span className="font-semibold text-white text-sm block truncate">
                  {user.display_name}
                </span>
                <span className="text-xs text-slate-500 block truncate">{user.email}</span>
              </div>

              <div className="p-3.5 rounded-xl bg-slate-950/50 border border-slate-800">
                <span className="text-xs text-slate-400 block mb-1">Study Track</span>
                <span className="font-mono font-bold text-indigo-400 text-sm block">
                  {user.arm}
                </span>
                <span className="text-xs text-slate-500 block">Balanced allocation</span>
              </div>

              <div className="p-3.5 rounded-xl bg-slate-950/50 border border-slate-800">
                <span className="text-xs text-slate-400 block mb-1">Consent Date</span>
                <span className="text-sm font-medium text-slate-200 block">
                  {user.consent_at
                    ? new Date(user.consent_at).toLocaleDateString()
                    : "Not provided yet"}
                </span>
                {!user.consent_at && (
                  <Link
                    href="/consent"
                    className="text-xs text-amber-400 underline hover:text-amber-300 block mt-1"
                  >
                    Provide consent now
                  </Link>
                )}
              </div>
            </div>

            {/* Right to be forgotten (D11 privacy) */}
            <div className="pt-4 border-t border-slate-800 flex items-center justify-between text-xs text-slate-500">
              <span>GDPR / Study Rights: You can request immediate erasure of your records.</span>
              <button
                type="button"
                onClick={handleDeleteAccount}
                disabled={deleting}
                className="text-rose-400 hover:text-rose-300 font-medium transition-colors"
              >
                {deleteConfirm ? "Click again to confirm delete" : "Delete My Data"}
              </button>
            </div>
          </div>
        )}

        {/* Closed Loop Architecture Modules */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-5 space-y-2.5 hover:border-slate-700 transition-colors">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/10 text-indigo-400 flex items-center justify-center font-bold text-sm">
              A
            </div>
            <h3 className="font-semibold text-white text-sm">Unified Learner State</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Bayesian Knowledge Tracing over 60 DSA concepts, paired with a 5-dimensional
              Gaussian psychometric trait vector (abstraction, load tolerance, depth, persistence,
              efficacy).
            </p>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-5 space-y-2.5 hover:border-slate-700 transition-colors">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/10 text-indigo-400 flex items-center justify-center font-bold text-sm">
              B
            </div>
            <h3 className="font-semibold text-white text-sm">Grounded Explainer</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              12 discrete presentation variants per concept card. Guaranteed factual grounding
              with precomputed cache, fast live LLM fallback, and deterministic template fail-safe.
            </p>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-5 space-y-2.5 hover:border-slate-700 transition-colors">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/10 text-indigo-400 flex items-center justify-center font-bold text-sm">
              C
            </div>
            <h3 className="font-semibold text-white text-sm">Feedback Analyzer</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              High-resolution client telemetry tracking viewport dwell, expansions, replays, and
              micro-checks to feed back into trait estimates and close the loop.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
