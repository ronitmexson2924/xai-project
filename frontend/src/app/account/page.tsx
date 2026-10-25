"use client";

import { AnimatePresence, motion } from "motion/react";
import { useRouter } from "next/navigation";
import React, { useState } from "react";
import { AppShell, PageLoading } from "@/components/AppShell";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ease, fadeUp, Stagger } from "@/components/ui/motion";
import { ApiException } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useLearnerGuard } from "@/lib/guards";

function date(value: string | null | undefined): string {
  return value ? new Date(value).toLocaleDateString([], { dateStyle: "long" }) : "Not yet";
}

export default function AccountPage() {
  const ready = useLearnerGuard({ need: "onboarding" });
  const { user, logout, withdraw } = useAuth();
  const router = useRouter();
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState<"logout" | "withdraw" | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!ready || !user) return <PageLoading />;

  const signOut = async () => {
    setBusy("logout");
    await logout();
    router.push("/");
  };

  const leave = async () => {
    setBusy("withdraw");
    setError(null);
    try {
      await withdraw();
      router.push("/");
    } catch (err) {
      setError(err instanceof ApiException ? err.message : "Could not withdraw. Please try again.");
      setBusy(null);
    }
  };

  const rows = [
    { label: "Name", value: user.display_name },
    { label: "Email", value: user.email },
    { label: "Joined", value: date(user.created_at) },
    { label: "Study consent given", value: date(user.consent_at) },
  ];

  return (
    <AppShell>
      <Stagger className="mx-auto max-w-2xl space-y-6">
        <motion.div variants={fadeUp}>
          <h1 className="text-2xl font-semibold tracking-tight text-fg">Account &amp; privacy</h1>
          <p className="mt-1 text-sm text-muted">Your details, and control over your data.</p>
        </motion.div>

        <motion.div variants={fadeUp}>
          <Card className="divide-y divide-line">
            {rows.map((r) => (
              <div key={r.label} className="flex flex-wrap items-center justify-between gap-2 px-5 py-4">
                <span className="text-sm text-muted">{r.label}</span>
                <span className="text-sm font-medium text-fg">{r.value}</span>
              </div>
            ))}
          </Card>
        </motion.div>

        <motion.div variants={fadeUp}>
          <Card className="space-y-3 p-5">
            <h2 className="font-semibold text-fg">Your data</h2>
            <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
              <li>Research exports use a pseudonym, never your name or email.</li>
              <li>We record your answers and how you use explanations, to adapt them and for the study.</li>
              <li>You can stop at any time without giving a reason.</li>
            </ul>
            <div className="pt-1">
              <Button variant="secondary" onClick={signOut} loading={busy === "logout"}>
                Log out
              </Button>
            </div>
          </Card>
        </motion.div>

        <motion.div variants={fadeUp}>
          <Card className="space-y-3 border-danger/30 p-5">
            <h2 className="font-semibold text-danger">Withdraw from the study</h2>
            <p className="text-sm text-muted">
              Your account stops working immediately and all your data is deleted by the next clean-up run. This cannot
              be undone.
            </p>
            {error && (
              <p role="alert" className="text-sm text-danger">
                {error}
              </p>
            )}
            <AnimatePresence mode="wait" initial={false}>
              {confirm ? (
                <motion.div
                  key="confirm"
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.2, ease }}
                  className="flex flex-wrap items-center gap-2 rounded-xl bg-danger-soft p-3"
                >
                  <span className="mr-auto text-sm text-fg">Are you sure?</span>
                  <Button variant="ghost" size="sm" onClick={() => setConfirm(false)}>
                    Cancel
                  </Button>
                  <Button variant="danger" size="sm" onClick={leave} loading={busy === "withdraw"}>
                    Yes, withdraw and delete my data
                  </Button>
                </motion.div>
              ) : (
                <motion.div key="ask" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                  <Button variant="secondary" onClick={() => setConfirm(true)} className="text-danger">
                    Withdraw
                  </Button>
                </motion.div>
              )}
            </AnimatePresence>
          </Card>
        </motion.div>
      </Stagger>
    </AppShell>
  );
}
