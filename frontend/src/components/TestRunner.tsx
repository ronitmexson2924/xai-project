"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import React, { useEffect, useState } from "react";
import { ApiException, useAuth } from "@/lib/auth-context";
import { api, PublicItem } from "@/lib/api";
import { ItemCard } from "./ItemCard";

/** The pre- or post-test (EVALUATION_PLAN H4): every item once, no feedback on correctness, and
 * the learner model is not updated. Items already answered are skipped by the server (409). */
export function TestRunner({ phase }: { phase: "pretest" | "posttest" }) {
  const router = useRouter();
  const { user, isLoading } = useAuth();
  const [items, setItems] = useState<PublicItem[]>([]);
  const [index, setIndex] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (isLoading) return;
    if (!user) router.push("/login");
    else if (!user.consent_at) router.push("/consent");
  }, [user, isLoading, router]);

  useEffect(() => {
    if (!user?.consent_at) return;
    api.items
      .test(phase)
      .then((list) => setItems(list))
      .catch(() => setError("The test could not be loaded."))
      .finally(() => setLoaded(true));
  }, [user, phase]);

  const answer = async (response: string, latencyMs: number) => {
    const item = items[index];
    if (!item || busy) return;
    setBusy(true);
    setError(null);
    try {
      await api.attempts.submit({ item_id: item.id, response, latency_ms: latencyMs, hints_used: 0 });
      setIndex((i) => i + 1);
    } catch (err) {
      if (err instanceof ApiException && err.code === "ALREADY_ANSWERED") {
        setIndex((i) => i + 1);
      } else {
        setError(err instanceof ApiException ? err.message : "Could not save your answer.");
      }
    } finally {
      setBusy(false);
    }
  };

  const title = phase === "pretest" ? "Starting quiz" : "Final quiz";
  const done = loaded && index >= items.length;

  return (
    <main className="mx-auto min-h-screen max-w-3xl space-y-6 bg-slate-950 px-4 py-10 text-slate-100">
      <h1 className="text-2xl font-bold">{title}</h1>
      <p className="text-sm text-slate-400">
        {items.length} short questions. You will not see whether each answer is right: this quiz
        measures where you are, so please answer on your own without looking anything up.
      </p>
      {error && <p role="alert" className="text-sm text-rose-300">{error}</p>}
      {!done && items[index] && (
        <>
          <p className="text-xs text-slate-500">
            Question {index + 1} of {items.length}
          </p>
          <ItemCard key={items[index].id} item={items[index]} onAnswer={answer} isSubmitting={busy} />
        </>
      )}
      {done && (
        <div className="space-y-4 rounded-2xl border border-emerald-500/30 bg-emerald-950/30 p-6">
          <p className="font-semibold text-emerald-200">Thank you, that is the whole quiz.</p>
          <Link href={phase === "pretest" ? "/session" : "/"} className="inline-block rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-indigo-500">
            {phase === "pretest" ? "Start practising →" : "Back to home"}
          </Link>
        </div>
      )}
    </main>
  );
}
