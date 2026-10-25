"use client";

import Link from "next/link";
import React, { useEffect, useState } from "react";
import Navbar from "@/components/Navbar";
import { Markdown } from "@/components/Markdown";
import { api, ApiException, TestOut, TestPhase } from "@/lib/api";
import { useLearnerGuard } from "@/lib/guards";

export function TestRunner({ phase }: { phase: TestPhase }) {
  const ready = useLearnerGuard();
  const [test, setTest] = useState<TestOut | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [state, setState] = useState<"loading" | "ready" | "confirm" | "sending" | "done">("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ready) return;
    api.tests
      .get(phase)
      .then((t) => {
        setTest(t);
        setState(t.submitted ? "done" : "ready");
      })
      .catch((err) => setError(err instanceof ApiException ? err.message : "Could not load the test."));
  }, [ready, phase]);

  const unanswered = test ? test.items.filter((i) => !answers[i.id]?.trim()).length : 0;

  const submit = async () => {
    if (unanswered > 0 && state !== "confirm") {
      setState("confirm");
      return;
    }
    setState("sending");
    setError(null);
    try {
      await api.tests.submit(phase, answers);
      setState("done");
    } catch (err) {
      setError(err instanceof ApiException ? err.message : "Could not submit. Please try again.");
      setState("ready");
    }
  };

  const title = phase === "pretest" ? "Pre-test" : "Post-test";
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <Navbar />
      <main className="max-w-3xl mx-auto px-4 py-8 space-y-6">
        <h1 className="text-2xl font-bold text-white">{title}</h1>
        {error && (
          <p role="alert" className="text-sm text-rose-300">
            {error}
          </p>
        )}
        {state === "done" ? (
          <div className="rounded-2xl border border-emerald-500/30 bg-emerald-950/20 p-6 space-y-3" data-testid="test-done">
            <p className="text-sm text-emerald-200">Thanks, your {title.toLowerCase()} is submitted.</p>
            <Link href={phase === "pretest" ? "/session" : "/"} className="inline-block text-sm font-semibold px-4 py-2 rounded-xl bg-indigo-600 text-white">
              {phase === "pretest" ? "Start learning →" : "Back to home"}
            </Link>
          </div>
        ) : (
          test && (
            <>
              <p className="text-sm text-slate-400">
                {test.items.length} questions. Answer what you can; you can submit only once and will not
                see a score.
              </p>
              <ol className="space-y-5">
                {test.items.map((item, n) => (
                  <li key={item.id} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 space-y-3">
                    <div className="text-xs text-slate-500">Question {n + 1}</div>
                    <Markdown text={item.stem} className="text-sm text-slate-100" />
                    {item.options.length > 0 ? (
                      <div className="space-y-2" role="radiogroup" aria-label={`Question ${n + 1}`}>
                        {item.options.map((opt) => (
                          <label key={opt} className="flex items-start gap-2 text-sm text-slate-300 cursor-pointer">
                            <input
                              type="radio"
                              name={item.id}
                              value={opt}
                              checked={answers[item.id] === opt}
                              onChange={() => setAnswers((a) => ({ ...a, [item.id]: opt }))}
                              className="mt-1"
                            />
                            <span>{opt}</span>
                          </label>
                        ))}
                      </div>
                    ) : (
                      <input
                        type="text"
                        maxLength={2000}
                        aria-label={`Answer to question ${n + 1}`}
                        value={answers[item.id] ?? ""}
                        onChange={(e) => setAnswers((a) => ({ ...a, [item.id]: e.target.value }))}
                        className="w-full rounded-xl border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm"
                      />
                    )}
                  </li>
                ))}
              </ol>
              <div className="flex items-center justify-between gap-3">
                {state === "confirm" && (
                  <span className="text-xs text-amber-300">
                    {unanswered} question(s) unanswered. They will count as wrong. Submit anyway?
                  </span>
                )}
                <button
                  type="button"
                  onClick={submit}
                  disabled={state === "sending"}
                  className="ml-auto px-6 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-sm font-semibold text-white disabled:opacity-50"
                >
                  {state === "sending" ? "Submitting…" : state === "confirm" ? "Submit anyway" : "Submit"}
                </button>
              </div>
            </>
          )
        )}
      </main>
    </div>
  );
}
