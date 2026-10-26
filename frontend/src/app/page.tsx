"use client";

import { motion } from "motion/react";
import React from "react";
import { ButtonLink } from "@/components/ui/Button";
import { Logo } from "@/components/ui/Logo";
import { ease, fadeUp, Stagger } from "@/components/ui/motion";
import { useAuth } from "@/lib/auth-context";
import { homeFor } from "@/lib/routes";

const FEATURES = [
  {
    title: "A map, not a playlist",
    body: "63 concepts linked by what you need first. Your next question is picked from what you know, not from a fixed syllabus.",
    icon: (
      <path d="M5 7a2 2 0 1 0 0-4 2 2 0 0 0 0 4Zm14 0a2 2 0 1 0 0-4 2 2 0 0 0 0 4Zm-7 14a2 2 0 1 0 0-4 2 2 0 0 0 0 4ZM6.2 6.6 11 17.3M17.8 6.6 13 17.3" />
    ),
  },
  {
    title: "Explanations that fit",
    body: "Example first or rule first, short or detailed. The style adapts to what actually helps you, and keeps learning from your feedback.",
    icon: <path d="M4 6h16M4 12h10M4 18h7m9-4-3 3-1.5-1.5" />,
  },
  {
    title: "Always shows its reasoning",
    body: "Every recommendation comes with “Why this?”: the evidence, what would change it, and why the explanation looks the way it does.",
    icon: <path d="M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-6v.01M12 12a2 2 0 1 0-2-2" />,
  },
];

const STEPS = [
  ["Tell us how you learn", "Twenty quick statements set a starting point."],
  ["Practise what is next", "Short questions with explanations shaped to you."],
  ["See why, and what changed", "Your progress and the reasons behind it, in plain words."],
];

export default function Landing() {
  const { user } = useAuth();
  const cta = user ? { href: homeFor(user), label: "Continue" } : { href: "/signup", label: "Get started" };

  return (
    <div className="relative min-h-screen overflow-hidden bg-bg">
      <div aria-hidden className="bg-grid pointer-events-none absolute inset-x-0 top-0 h-[640px]" />
      <div aria-hidden className="pointer-events-none absolute left-1/2 top-[-200px] h-[480px] w-[880px] -translate-x-1/2 rounded-full bg-primary/15 blur-3xl" />

      <header className="relative z-10 mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Logo />
        <nav aria-label="Account" className="flex items-center gap-2">
          {user ? (
            <ButtonLink href={homeFor(user)} variant="secondary" size="sm">
              Open app
            </ButtonLink>
          ) : (
            <>
              <ButtonLink href="/login" variant="ghost" size="sm">
                Log in
              </ButtonLink>
              <ButtonLink href="/signup" size="sm">
                Sign up
              </ButtonLink>
            </>
          )}
        </nav>
      </header>

      <main className="relative z-10">
        <section className="mx-auto max-w-3xl px-4 pb-20 pt-16 text-center sm:px-6 sm:pt-24">
          <Stagger gap={0.08}>
            <motion.p variants={fadeUp} className="mb-5 inline-flex items-center gap-2 rounded-full border border-line bg-surface/70 px-3 py-1 text-xs font-medium text-muted backdrop-blur">
              <span className="h-1.5 w-1.5 rounded-full bg-success" aria-hidden />
              Adaptive · explainable · private
            </motion.p>
            <motion.h1 variants={fadeUp} className="text-4xl font-semibold tracking-tight text-fg sm:text-6xl sm:leading-[1.05]">
              Learn algorithms the way
              <br className="hidden sm:block" /> <span className="text-primary">you</span> learn best.
            </motion.h1>
            <motion.p variants={fadeUp} className="mx-auto mt-6 max-w-xl text-base leading-relaxed text-muted sm:text-lg">
              Concept is a tutor for data structures and algorithms that chooses your next step, adapts how it
              explains, and always tells you why.
            </motion.p>
            <motion.div variants={fadeUp} className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <ButtonLink href={cta.href} size="lg" className="w-full sm:w-auto">
                {cta.label}
                <span aria-hidden>→</span>
              </ButtonLink>
              {!user && (
                <ButtonLink href="/login" size="lg" variant="secondary" className="w-full sm:w-auto">
                  I have an account
                </ButtonLink>
              )}
            </motion.div>
          </Stagger>

          <HeroPreview />
        </section>

        <section aria-labelledby="features" className="border-t border-line bg-surface/50">
          <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
            <h2 id="features" className="sr-only">
              What makes it different
            </h2>
            <div className="grid gap-6 md:grid-cols-3">
              {FEATURES.map((f, i) => (
                <motion.article
                  key={f.title}
                  initial={{ opacity: 0, y: 16 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, margin: "-80px" }}
                  transition={{ duration: 0.5, ease, delay: i * 0.08 }}
                  className="rounded-xl border border-line bg-surface p-6 shadow-card"
                >
                  <span className="mb-4 inline-flex h-10 w-10 items-center justify-center rounded-xl bg-primary-soft text-primary">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                      {f.icon}
                    </svg>
                  </span>
                  <h3 className="text-base font-semibold text-fg">{f.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-muted">{f.body}</p>
                </motion.article>
              ))}
            </div>
          </div>
        </section>

        <section aria-labelledby="how" className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
          <h2 id="how" className="text-center text-2xl font-semibold tracking-tight text-fg sm:text-3xl">
            How it works
          </h2>
          <ol className="mt-12 grid gap-8 md:grid-cols-3">
            {STEPS.map(([title, body], i) => (
              <motion.li
                key={title}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-80px" }}
                transition={{ duration: 0.5, ease, delay: i * 0.1 }}
                className="relative"
              >
                <span className="text-sm font-medium text-primary">0{i + 1}</span>
                <h3 className="mt-2 text-lg font-semibold text-fg">{title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-muted">{body}</p>
              </motion.li>
            ))}
          </ol>
          <div className="mt-16 flex justify-center">
            <ButtonLink href={cta.href} size="lg">
              {user ? "Continue" : "Start learning"} <span aria-hidden>→</span>
            </ButtonLink>
          </div>
        </section>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-2 px-4 py-6 text-xs text-subtle sm:flex-row sm:px-6">
          <span>Part of a research study on adaptive, explainable tutoring.</span>
          <span>No ads, no third-party trackers. You can delete your data at any time.</span>
        </div>
      </footer>
    </div>
  );
}

/** A static, illustrative preview of the learning screen (no real data). */
function HeroPreview() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 32, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.8, ease, delay: 0.35 }}
      className="relative mx-auto mt-16 max-w-2xl text-left"
      aria-hidden
    >
      <div className="rounded-xl border border-line bg-surface p-5 shadow-pop sm:p-6">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-subtle">Recursion · base case</span>
          <span className="rounded-full bg-primary-soft px-2 py-0.5 text-[11px] font-medium text-primary">example first</span>
        </div>
        <pre className="mt-4 overflow-hidden rounded-lg bg-surface-2 p-3 font-mono text-[13px] leading-relaxed text-fg">
{`def fact(n):
    if n == 0:
        return 1
    return n * fact(n - 1)`}
        </pre>
        <p className="mt-4 text-sm font-medium text-fg">What does fact(0) return?</p>
        <div className="mt-3 grid grid-cols-3 gap-2">
          {["0", "1", "It never returns"].map((o, i) => (
            <div key={o} className={`rounded-lg border px-3 py-2 text-sm ${i === 1 ? "border-primary bg-primary-soft text-fg" : "border-line text-muted"}`}>
              {o}
            </div>
          ))}
        </div>
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease, delay: 1.1 }}
          className="mt-4 rounded-xl border border-line bg-surface-2 p-3"
        >
          <p className="text-xs font-semibold text-fg">Why this?</p>
          <p className="mt-1 text-xs leading-relaxed text-muted">
            Your answers suggest base cases need one more look before recursive calls. Two correct answers here
            and you move on.
          </p>
        </motion.div>
      </div>
    </motion.div>
  );
}
