"use client";

import { useSearchParams } from "next/navigation";
import React, { Suspense, useEffect, useState } from "react";
import { AppShell, PageLoading } from "@/components/AppShell";
import { ReportSkeleton, ReportView } from "@/components/report/ReportView";
import { ButtonLink } from "@/components/ui/Button";
import { api, ApiException, UserReport } from "@/lib/api";
import { useLearnerGuard } from "@/lib/guards";

/** An admin's view of one learner's report, by pseudonym only: no name or email is ever shown. */
function AdminReport() {
  const isAdmin = useLearnerGuard({ requireAdmin: true });
  const pseudonym = useSearchParams().get("p") ?? "";
  const [report, setReport] = useState<UserReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isAdmin || !pseudonym) return;
    let live = true;
    api.admin
      .learnerReport(pseudonym)
      .then((r) => live && setReport(r))
      .catch((err) => live && setError(err instanceof ApiException ? err.message : "Could not load this report."));
    return () => {
      live = false;
    };
  }, [isAdmin, pseudonym]);

  if (!isAdmin) return <PageLoading />;
  return (
    <AppShell>
      <div className="mx-auto max-w-5xl space-y-6">
        <ButtonLink href="/admin" variant="ghost" size="sm" className="no-print -ml-3">
          <span aria-hidden>←</span> Back to admin
        </ButtonLink>
        {!pseudonym || error ? (
          <p role="alert" className="rounded-xl border border-danger/30 bg-danger-soft p-4 text-sm text-danger">
            {error ?? "No learner selected."}
          </p>
        ) : report ? (
          <ReportView report={report} heading={`Learner ${pseudonym}`} subtitle="Admin view, by pseudonym" learnerView={false} />
        ) : (
          <ReportSkeleton />
        )}
      </div>
    </AppShell>
  );
}

export default function AdminReportPage() {
  return (
    <Suspense fallback={<PageLoading />}>
      <AdminReport />
    </Suspense>
  );
}
