"use client";

import { motion } from "motion/react";
import React, { useEffect, useState } from "react";
import { AppShell, PageLoading } from "@/components/AppShell";
import { Badge } from "@/components/ui/Badge";
import { ButtonLink } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { fadeUp, Stagger } from "@/components/ui/motion";
import { api, TestOut } from "@/lib/api";
import { useLearnerGuard } from "@/lib/guards";

const ABOUT = {
  pretest: { title: "Pre-test", when: "Take this before you start learning." },
  posttest: { title: "Post-test", when: "Take this at the end of the study." },
};

export default function TestsIndex() {
  const ready = useLearnerGuard();
  const [tests, setTests] = useState<TestOut[] | null>(null);

  useEffect(() => {
    if (!ready) return;
    Promise.all([api.tests.get("pretest"), api.tests.get("posttest")])
      .then(setTests)
      .catch(() => setTests([]));
  }, [ready]);

  if (!ready) return <PageLoading />;
  return (
    <AppShell>
      <Stagger className="mx-auto max-w-3xl space-y-6">
        <motion.div variants={fadeUp}>
          <h1 className="text-2xl font-semibold tracking-tight text-fg">Tests</h1>
          <p className="mt-1 max-w-xl text-sm text-muted">
            Two short tests measure how much you learn during the study. Each is taken once, is not graded and shows no
            score.
          </p>
        </motion.div>
        {!tests && <div className="h-24 animate-pulse rounded-2xl bg-surface-2" aria-busy />}
        {tests?.map((t) => (
          <motion.div key={t.phase} variants={fadeUp}>
            <Card className="flex flex-wrap items-center justify-between gap-4 p-5 sm:p-6">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="font-semibold text-fg">{ABOUT[t.phase as keyof typeof ABOUT].title}</h2>
                  {t.submitted && <Badge tone="success">Submitted</Badge>}
                </div>
                <p className="mt-0.5 text-sm text-muted">
                  {t.items.length} questions · {ABOUT[t.phase as keyof typeof ABOUT].when}
                </p>
              </div>
              {!t.submitted && t.items.length > 0 && (
                <ButtonLink href={`/tests/${t.phase}`} variant={t.phase === "pretest" ? "primary" : "secondary"}>
                  Start
                </ButtonLink>
              )}
            </Card>
          </motion.div>
        ))}
      </Stagger>
    </AppShell>
  );
}
