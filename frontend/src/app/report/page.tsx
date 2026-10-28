"use client";

import React, { useEffect, useState } from "react";
import { AppShell, PageLoading } from "@/components/AppShell";
import { ReportSkeleton, ReportView } from "@/components/report/ReportView";
import { Button } from "@/components/ui/Button";
import { api, ApiException, UserReport } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useLearnerGuard } from "@/lib/guards";

/** The learner's own report: their profile and why the AI model predicts what it does for them. */
export default function ReportPage() {
  const ready = useLearnerGuard();
  const { user } = useAuth();
  const [report, setReport] = useState<UserReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = React.useCallback(() => {
    setError(null);
    api.learners
      .getReport()
      .then(setReport)
      .catch((err) => setError(err instanceof ApiException ? err.message : "Could not load your report."));
  }, []);

  useEffect(() => {
    if (!ready) return;
    const timer = setTimeout(load, 0);
    return () => clearTimeout(timer);
  }, [ready, load]);

  if (!ready) return <PageLoading />;
  return (
    <AppShell>
      <div className="mx-auto max-w-5xl">
        {error ? (
          <div role="alert" className="flex items-center justify-between gap-3 rounded-xl border border-danger/30 bg-danger-soft p-4 text-sm text-danger">
            <span>{error}</span>
            <Button size="sm" variant="secondary" onClick={load}>
              Retry
            </Button>
          </div>
        ) : report ? (
          <ReportView report={report} heading={user?.display_name ? `${user.display_name}'s learning profile` : "Your learning profile"} learnerView />
        ) : (
          <ReportSkeleton />
        )}
      </div>
    </AppShell>
  );
}
