"use client";

import Link from "next/link";
import React, { useEffect, useState } from "react";
import { api, ApiException, GlobalAttributions, LearnerListing } from "@/lib/api";
import { Card } from "../ui/Card";
import { Beeswarm } from "./ProfileCharts";

const ARM: Record<string, string> = { closed_loop: "Closed loop", static_personalized: "Static personalised", generic: "Generic" };

/**
 * Admin-only explainability: every learner's report, listed by pseudonym (never by name or email),
 * and the cross-learner SHAP beeswarm, which belongs here rather than in anyone's own report.
 */
export function AdminXai() {
  const [learners, setLearners] = useState<LearnerListing[] | null>(null);
  const [global, setGlobal] = useState<GlobalAttributions | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [all, setAll] = useState(false);

  useEffect(() => {
    let live = true;
    const fail = (err: unknown) => live && setError(err instanceof ApiException ? err.message : "Could not load the explainability data.");
    api.admin.learners().then((l) => live && setLearners(l)).catch(fail);
    api.admin.globalXai().then((g) => live && setGlobal(g)).catch(fail);
    return () => {
      live = false;
    };
  }, []);

  const shown = learners ? (all ? learners : learners.slice(0, 12)) : [];
  return (
    <div className="space-y-6" data-testid="admin-xai">
      <Card className="p-6">
        <h2 className="font-semibold text-fg">Learner reports</h2>
        <p className="mt-0.5 text-sm text-muted">Each learner&apos;s profile and model explanations, by pseudonym. Most recently active first.</p>
        {error && <p role="alert" className="mt-4 text-sm text-danger">{error}</p>}
        {!learners && !error && <div className="mt-4 h-24 animate-pulse rounded-lg bg-surface-2" aria-busy />}
        {learners && (
          <div className="relative mt-4 overflow-x-auto" tabIndex={0} role="region" aria-label="Learners by pseudonym">
            <table className="w-full min-w-[520px] text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs text-subtle">
                  <th className="py-2 pr-3 font-medium">Pseudonym</th>
                  <th className="py-2 pr-3 font-medium">Arm</th>
                  <th className="py-2 pr-3 text-right font-medium">Answers</th>
                  <th className="py-2 pr-3 font-medium">Last active</th>
                  <th className="py-2 font-medium" />
                </tr>
              </thead>
              <tbody>
                {shown.map((l) => (
                  <tr key={l.pseudonym} className="border-b border-line/60">
                    <td className="py-2 pr-3 font-mono text-[13px] text-fg">{l.pseudonym}</td>
                    <td className="py-2 pr-3 text-muted">{ARM[l.arm] ?? l.arm}</td>
                    <td className="py-2 pr-3 text-right tabular-nums text-muted">{l.attempts}</td>
                    <td className="py-2 pr-3 text-muted">{l.last_active ? new Date(l.last_active).toLocaleDateString() : "—"}</td>
                    <td className="py-2 text-right">
                      <Link href={`/admin/report?p=${l.pseudonym}`} className="text-sm font-medium text-primary hover:text-primary-hover">
                        Open report<span className="sr-only"> for {l.pseudonym}</span> →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {learners.length > 12 && (
              <button type="button" onClick={() => setAll((a) => !a)} className="mt-3 text-xs font-medium text-primary hover:text-primary-hover">
                {all ? "Show the 12 most recent" : `Show all ${learners.length} learners`}
              </button>
            )}
          </div>
        )}
      </Card>
      {global ? (
        global.predictions > 0 ? (
          <Beeswarm data={global} />
        ) : (
          <Card className="p-6 text-sm text-muted">No answered questions yet, so there is no cross-learner view.</Card>
        )
      ) : (
        !error && <div className="h-72 animate-pulse rounded-xl bg-surface-2" aria-busy aria-label="Loading the cross-learner view" />
      )}
    </div>
  );
}
