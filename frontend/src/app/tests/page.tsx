"use client";

import Link from "next/link";
import React, { useEffect, useState } from "react";
import Navbar from "@/components/Navbar";
import { api, TestOut } from "@/lib/api";
import { useLearnerGuard } from "@/lib/guards";

export default function TestsIndex() {
  const ready = useLearnerGuard();
  const [tests, setTests] = useState<TestOut[] | null>(null);

  useEffect(() => {
    if (!ready) return;
    Promise.all([api.tests.get("pretest"), api.tests.get("posttest")])
      .then(setTests)
      .catch(() => setTests([]));
  }, [ready]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <Navbar />
      <main className="max-w-2xl mx-auto px-4 py-10 space-y-6">
        <h1 className="text-2xl font-bold text-white">Tests</h1>
        <p className="text-sm text-slate-400">
          Take the pre-test before you start and the post-test at the end of the study. Each is taken
          once, is not graded and shows no score.
        </p>
        {tests?.map((t) => (
          <div key={t.phase} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 flex items-center justify-between">
            <div>
              <div className="font-semibold text-white">{t.phase === "pretest" ? "Pre-test" : "Post-test"}</div>
              <div className="text-xs text-slate-400">{t.items.length} questions</div>
            </div>
            {t.submitted ? (
              <span className="text-xs text-emerald-400">Submitted</span>
            ) : (
              <Link href={`/tests/${t.phase}`} className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-indigo-600 text-white">
                Start
              </Link>
            )}
          </div>
        ))}
      </main>
    </div>
  );
}
