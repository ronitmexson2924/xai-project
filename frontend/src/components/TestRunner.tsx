"use client";

import { AnimatePresence, motion } from "motion/react";
import React, { useEffect, useState } from "react";
import { AppShell, PageLoading } from "@/components/AppShell";
import { Markdown } from "@/components/Markdown";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { cn } from "@/components/ui/cn";
import { ease } from "@/components/ui/motion";
import { Progress } from "@/components/ui/Progress";
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

  const total = test?.items.length ?? 0;
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

  if (!ready) return <PageLoading />;
  const title = phase === "pretest" ? "Pre-test" : "Post-test";

  return (
    <AppShell>
      <div className="mx-auto max-w-3xl space-y-6">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-primary">Study test</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-fg">{title}</h1>
        </div>

        {error && (
          <p role="alert" className="rounded-xl border border-danger/30 bg-danger-soft p-4 text-sm text-danger">
            {error}
          </p>
        )}

        {state === "loading" && !error && <div className="h-40 animate-pulse rounded-xl bg-surface-2" aria-busy />}

        {state === "done" ? (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, ease }}>
            <Card className="flex flex-col items-center gap-4 p-10 text-center" data-testid="test-done">
              <motion.span
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: "spring", stiffness: 300, damping: 18, delay: 0.1 }}
                className="flex h-12 w-12 items-center justify-center rounded-full bg-success-soft text-xl text-success"
                aria-hidden
              >
                ✓
              </motion.span>
              <div>
                <h2 className="text-lg font-semibold text-fg">Thanks, your {title.toLowerCase()} is submitted.</h2>
                <p className="mt-1 text-sm text-muted">There is no grade. Your answers are only used for the study.</p>
              </div>
              <ButtonLink href={phase === "pretest" ? "/session" : "/dashboard"} size="lg">
                {phase === "pretest" ? "Start learning →" : "Back to dashboard"}
              </ButtonLink>
            </Card>
          </motion.div>
        ) : (
          test && (
            <>
              <div className="sticky top-14 z-30 -mx-4 space-y-2 border-b border-line bg-bg/85 px-4 py-3 backdrop-blur-xl sm:-mx-6 sm:px-6">
                <div className="flex items-center justify-between text-sm">
                  <p className="text-muted">
                    {total} questions. Answer what you can; you can submit only once and will not see a score.
                  </p>
                  <span className="flex-none pl-3 tabular-nums text-fg">
                    {total - unanswered}/{total}
                  </span>
                </div>
                <Progress value={total ? (total - unanswered) / total : 0} label="Questions answered" />
              </div>

              <ol className="space-y-4">
                {test.items.map((item, n) => (
                  <motion.li
                    key={item.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.35, ease, delay: Math.min(n * 0.03, 0.4) }}
                  >
                    <Card className="space-y-4 p-5 sm:p-6">
                      <p className="text-xs font-medium text-subtle">
                        Question {n + 1} of {total}
                      </p>
                      <Markdown text={item.stem} className="text-[15px] font-medium leading-relaxed text-fg" />
                      {item.options.length > 0 ? (
                        <div className="space-y-2" role="radiogroup" aria-label={`Question ${n + 1}`}>
                          {item.options.map((opt) => {
                            const checked = answers[item.id] === opt;
                            return (
                              <label
                                key={opt}
                                className={cn(
                                  "flex cursor-pointer items-start gap-3 rounded-xl border p-3 text-sm transition-colors",
                                  checked ? "border-primary bg-primary-soft" : "border-line hover:bg-surface-2"
                                )}
                              >
                                <input
                                  type="radio"
                                  name={item.id}
                                  value={opt}
                                  checked={checked}
                                  onChange={() => setAnswers((a) => ({ ...a, [item.id]: opt }))}
                                  className="mt-0.5 h-4 w-4 accent-[var(--primary)]"
                                />
                                <span className="text-fg">{opt}</span>
                              </label>
                            );
                          })}
                        </div>
                      ) : (
                        <input
                          type="text"
                          maxLength={2000}
                          aria-label={`Answer to question ${n + 1}`}
                          placeholder="Your answer"
                          value={answers[item.id] ?? ""}
                          onChange={(e) => setAnswers((a) => ({ ...a, [item.id]: e.target.value }))}
                          className="h-11 w-full rounded-lg border border-line bg-surface px-3.5 font-mono text-sm text-fg focus:border-primary focus:outline-none focus:ring-4 focus:ring-primary/15"
                        />
                      )}
                    </Card>
                  </motion.li>
                ))}
              </ol>

              <div className="flex flex-wrap items-center justify-end gap-3 pb-8">
                <AnimatePresence>
                  {state === "confirm" && (
                    <motion.span
                      role="alert"
                      initial={{ opacity: 0, x: 8 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0 }}
                      className="text-sm text-warning"
                    >
                      {unanswered} question(s) unanswered. They will count as wrong. Submit anyway?
                    </motion.span>
                  )}
                </AnimatePresence>
                <Button size="lg" onClick={submit} loading={state === "sending"}>
                  {state === "confirm" ? "Submit anyway" : "Submit"}
                </Button>
              </div>
            </>
          )
        )}
      </div>
    </AppShell>
  );
}
