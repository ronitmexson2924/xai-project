"use client";

import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { PageLoading } from "@/components/AppShell";
import { Button } from "@/components/ui/Button";
import { Logo } from "@/components/ui/Logo";
import { Progress } from "@/components/ui/Progress";
import { cn } from "@/components/ui/cn";
import { ease } from "@/components/ui/motion";
import { api, ApiException, QuestionnaireItem } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useLearnerGuard } from "@/lib/guards";

const LIKERT = [
  { value: 1, label: "Strongly disagree" },
  { value: 2, label: "Disagree" },
  { value: 3, label: "Neutral" },
  { value: 4, label: "Agree" },
  { value: 5, label: "Strongly agree" },
];

type Step = "consent" | "questions" | "done";

export default function OnboardingPage() {
  const ready = useLearnerGuard({ need: "onboarding" });
  const { user, giveConsent, markOnboarded, logout } = useAuth();
  const router = useRouter();
  const [chosen, setStep] = useState<Step | null>(null);
  // finished users who land here go to the dashboard; "done" is only shown right after finishing
  const finished = Boolean(user?.onboarded && user.consent_at) && chosen === null;
  const step: Step | null = chosen ?? (user && !finished ? (user.consent_at ? "questions" : "consent") : null);

  useEffect(() => {
    if (ready && finished) router.replace("/dashboard");
  }, [ready, finished, router]);

  if (!ready || !step) return <PageLoading />;

  const stepIndex = { consent: 0, questions: 1, done: 2 }[step];
  return (
    <div className="flex min-h-screen flex-col bg-bg">
      <header className="mx-auto flex h-16 w-full max-w-3xl items-center justify-between px-4 sm:px-6">
        <Logo href="/" />
        <ol className="flex items-center gap-2" aria-label="Setup progress">
          {["Consent", "About you", "Ready"].map((label, i) => (
            <li key={label} className="flex items-center gap-2">
              <span
                aria-current={i === stepIndex ? "step" : undefined}
                className={cn(
                  "h-1.5 rounded-full transition-all duration-500",
                  i < stepIndex ? "w-6 bg-accent" : i === stepIndex ? "w-10 bg-accent" : "w-6 bg-line"
                )}
              />
              <span className="sr-only">
                {label}
                {i < stepIndex ? " (done)" : i === stepIndex ? " (current)" : ""}
              </span>
            </li>
          ))}
        </ol>
      </header>
      <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col px-4 pb-16 pt-6 sm:px-6 sm:pt-12">
        <AnimatePresence mode="wait">
          {step === "consent" && (
            <Consent
              key="consent"
              onAgree={async () => {
                await giveConsent();
                setStep("questions");
              }}
              onDecline={async () => {
                await logout();
                router.push("/");
              }}
            />
          )}
          {step === "questions" && (
            <Questions
              key="questions"
              onDone={() => {
                markOnboarded();
                setStep("done");
              }}
            />
          )}
          {step === "done" && <Done key="done" name={user?.display_name ?? ""} />}
        </AnimatePresence>
      </main>
    </div>
  );
}

const panel = {
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.45, ease } },
  exit: { opacity: 0, y: -12, transition: { duration: 0.25 } },
};

function Consent({ onAgree, onDecline }: { onAgree: () => Promise<void>; onDecline: () => Promise<void> }) {
  const [agreed, setAgreed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const agree = async () => {
    setBusy(true);
    setError(null);
    try {
      await onAgree();
    } catch (err) {
      setError(err instanceof ApiException ? err.message : "Could not save your answer. Please try again.");
      setBusy(false);
    }
  };

  return (
    <motion.section {...panel} aria-labelledby="consent-title">
      <h1 id="consent-title" className="text-3xl font-semibold tracking-tight text-fg">
        Before we start
      </h1>
      <p className="mt-2 text-muted">This app is part of a research study. Here is what that means for you.</p>
      <ul className="mt-8 space-y-5">
        {[
          ["What you do", "Answer short questions on data structures and algorithms, and a short test at the start and at the end. Go at your own pace."],
          ["What we record", "Your answers, how you interact with explanations (for example how long one stays open, or a clarity rating), and a starting questionnaire about how you like to learn."],
          ["Your privacy", "Research data uses pseudonymous ids, never your name or email. No ads and no third-party trackers."],
          ["Fair comparison", "Participants use slightly different versions of the app, assigned at random. You will find out which one after the study."],
          ["Your choice", "Taking part is voluntary. You can withdraw at any time from your account page, and your data is deleted."],
        ].map(([title, body]) => (
          <li key={title} className="flex gap-4">
            <span className="mt-1 flex h-5 w-5 flex-none items-center justify-center rounded-full bg-accent-soft text-accent" aria-hidden>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                <path d="m5 12 5 5L20 7" />
              </svg>
            </span>
            <div>
              <h2 className="text-sm font-semibold text-fg">{title}</h2>
              <p className="mt-0.5 text-sm leading-relaxed text-muted">{body}</p>
            </div>
          </li>
        ))}
      </ul>
      <label className="mt-10 flex cursor-pointer items-start gap-3 rounded-xl border border-line bg-surface p-4 shadow-card">
        <input
          type="checkbox"
          checked={agreed}
          onChange={(e) => setAgreed(e.target.checked)}
          className="mt-0.5 h-4 w-4 accent-[var(--accent)]"
        />
        <span className="text-sm text-fg">I have read this and agree to take part in the study.</span>
      </label>
      {error && (
        <p role="alert" className="mt-3 text-sm text-danger">
          {error}
        </p>
      )}
      <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-between">
        <Button variant="ghost" onClick={onDecline}>
          Not now
        </Button>
        <Button size="lg" disabled={!agreed} loading={busy} onClick={agree}>
          Agree and continue
        </Button>
      </div>
    </motion.section>
  );
}

function Questions({ onDone }: { onDone: () => void }) {
  const [items, setItems] = useState<QuestionnaireItem[] | null>(null);
  const [index, setIndex] = useState(0);
  const [direction, setDirection] = useState(1);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.onboarding
      .getQuestionnaire()
      .then(setItems)
      .catch((err) => setError(err instanceof ApiException ? err.message : "Could not load the questions."));
  }, []);

  const total = items?.length ?? 0;
  const item = items?.[index];
  const answered = Object.keys(answers).length;
  const complete = total > 0 && answered === total;

  const go = useCallback(
    (to: number) => {
      if (to < 0 || to >= total) return;
      setDirection(to > index ? 1 : -1);
      setIndex(to);
    },
    [index, total]
  );

  const choose = useCallback(
    (value: number) => {
      if (!item) return;
      setAnswers((a) => ({ ...a, [item.id]: value }));
      if (index < total - 1) window.setTimeout(() => go(index + 1), 220);
    },
    [item, index, total, go]
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.metaKey || e.ctrlKey) return;
      const n = Number(e.key);
      if (n >= 1 && n <= 5) choose(n);
      else if (e.key === "ArrowLeft") go(index - 1);
      else if (e.key === "ArrowRight" && item && answers[item.id]) go(index + 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [choose, go, index, item, answers]);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.onboarding.submitQuestionnaire(answers);
      onDone();
    } catch (err) {
      setError(err instanceof ApiException ? err.message : "Could not save your answers. Please try again.");
      setBusy(false);
    }
  };

  const variants = useMemo(
    () => ({
      enter: (d: number) => ({ opacity: 0, x: d * 40 }),
      center: { opacity: 1, x: 0, transition: { duration: 0.35, ease } },
      exit: (d: number) => ({ opacity: 0, x: d * -40, transition: { duration: 0.2 } }),
    }),
    []
  );

  return (
    <motion.section {...panel} aria-labelledby="q-title" className="flex flex-1 flex-col">
      <div className="flex items-center justify-between text-sm text-muted">
        <span id="q-title">
          {item ? `Question ${index + 1} of ${total}` : "Loading questions…"}
        </span>
        <span className="hidden sm:inline">Press 1–5 to answer, ← to go back</span>
      </div>
      <Progress value={total ? answered / total : 0} label="Questionnaire progress" className="mt-3" />

      <div className="relative mt-10 min-h-[340px] flex-1">
        <AnimatePresence mode="wait" custom={direction}>
          {item && (
            <motion.div key={item.id} custom={direction} variants={variants} initial="enter" animate="center" exit="exit">
              <p className="text-xl font-medium leading-snug tracking-tight text-fg sm:text-2xl" data-testid="question-text">
                {item.text}
              </p>
              <div role="radiogroup" aria-label="How much do you agree?" className="mt-8 grid gap-2.5">
                {LIKERT.map((o) => {
                  const selected = answers[item.id] === o.value;
                  return (
                    <button
                      key={o.value}
                      type="button"
                      role="radio"
                      aria-checked={selected}
                      onClick={() => choose(o.value)}
                      className={cn(
                        "group flex items-center gap-4 rounded-xl border px-4 py-3.5 text-left transition-all duration-150",
                        selected
                          ? "border-accent bg-accent-soft shadow-card"
                          : "border-line bg-surface hover:border-line-strong hover:shadow-card"
                      )}
                    >
                      <span
                        className={cn(
                          "flex h-7 w-7 flex-none items-center justify-center rounded-md border text-xs font-semibold tabular-nums transition-colors",
                          selected ? "border-accent bg-accent text-accent-fg" : "border-line text-subtle group-hover:text-fg"
                        )}
                      >
                        {o.value}
                      </span>
                      <span className={cn("text-[15px]", selected ? "font-medium text-fg" : "text-muted group-hover:text-fg")}>{o.label}</span>
                    </button>
                  );
                })}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {error && (
        <p role="alert" className="mb-3 text-sm text-danger">
          {error}
        </p>
      )}
      <div className="mt-6 flex items-center justify-between">
        <Button variant="ghost" onClick={() => go(index - 1)} disabled={index === 0}>
          ← Back
        </Button>
        {complete ? (
          <Button size="lg" loading={busy} onClick={submit}>
            Finish
          </Button>
        ) : (
          <Button variant="secondary" onClick={() => go(index + 1)} disabled={!item || !answers[item.id] || index === total - 1}>
            Next →
          </Button>
        )}
      </div>
    </motion.section>
  );
}

function Done({ name }: { name: string }) {
  const router = useRouter();
  const first = name.split(" ")[0];
  return (
    <motion.section {...panel} className="flex flex-1 flex-col items-center justify-center text-center" aria-live="polite">
      <motion.div
        initial={{ scale: 0.6, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: "spring", stiffness: 260, damping: 18 }}
        className="flex h-16 w-16 items-center justify-center rounded-full bg-success-soft text-success"
      >
        <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <motion.path d="m5 12 5 5L20 7" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.5, delay: 0.2, ease }} />
        </svg>
      </motion.div>
      <h1 className="mt-6 text-3xl font-semibold tracking-tight text-fg">You’re all set{first ? `, ${first}` : ""}.</h1>
      <p className="mx-auto mt-3 max-w-md text-muted">
        Your answers set a starting point for how explanations are written. From here on, your feedback keeps
        tuning it, and you can always see why.
      </p>
      <Button size="lg" className="mt-10" onClick={() => router.push("/dashboard")}>
        Go to your dashboard →
      </Button>
    </motion.section>
  );
}
