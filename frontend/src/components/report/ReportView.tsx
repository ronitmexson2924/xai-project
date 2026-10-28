"use client";

import Link from "next/link";
import React from "react";
import type { UserReport } from "@/lib/api";
import { Button, ButtonLink } from "../ui/Button";
import { DecisionPlot, ShapWaterfall } from "./ShapCharts";
import { LimeBars, ShapVsLime } from "./LimeCharts";
import { LrpHeatmap, Radar } from "./ProfileCharts";
import { AgreementAndQuality, CounterfactualTable, XaiMatrix } from "./XaiTables";

const METHOD_NAME: Record<string, string> = {
  shap: "SHAP",
  lime: "LIME",
  lrp: "LRP",
  dice: "DiCE",
  shap_recent: "SHAP over recent questions",
  lrp_recent: "LRP over recent questions",
};

function Section({ title, hint, children, id }: { title: string; hint?: string; children: React.ReactNode; id: string }) {
  return (
    <section className="space-y-4" aria-labelledby={id}>
      <div>
        <h2 id={id} className="text-base font-semibold tracking-tight text-fg">
          {title}
        </h2>
        {hint && <p className="mt-0.5 text-sm text-muted">{hint}</p>}
      </div>
      {children}
    </section>
  );
}

/**
 * A learner's report: their profile (traits and mastery as radar charts) and the Explainability
 * section, i.e. why the AI model predicts what it does for them, explained by SHAP, LIME, LRP and
 * DiCE, with how far the methods agree and how good each explanation is. Shared by the learner's
 * own page and the admin view, which shows the same report under a pseudonym.
 */
export function ReportView({ report, heading, subtitle, learnerView }: { report: UserReport; heading: string; subtitle?: string; learnerView: boolean }) {
  const failed = report.methods.filter((m) => !m.ok);
  const generated = new Date(report.generated_at);
  return (
    <div className="space-y-10" data-testid="learner-report">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="label-caps">Learning profile</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-fg sm:text-3xl">{heading}</h1>
          <p className="mt-1.5 text-sm text-muted">
            {subtitle ? `${subtitle} · ` : ""}Generated {generated.toLocaleString()} from {report.recent_predictions} answered{" "}
            {report.recent_predictions === 1 ? "question" : "questions"}.
          </p>
        </div>
        <Button variant="secondary" onClick={() => window.print()} className="no-print">
          Download PDF
        </Button>
      </div>

      <p role="note" className="flex gap-3 rounded-xl border border-line bg-surface-2 p-4 text-sm leading-relaxed text-muted" data-testid="report-disclaimer">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="mt-0.5 flex-none text-subtle" aria-hidden>
          <circle cx="12" cy="12" r="9" />
          <path d="M12 11v5M12 8h.01" />
        </svg>
        <span>
          <strong className="font-medium text-fg">About this report.</strong> {report.disclaimer}
        </span>
      </p>

      <Section id="profile" title="Profile" hint="What the learner model currently believes. Each value is an estimate that updates with every answer.">
        <div className="grid gap-4 lg:grid-cols-2">
          <Radar
            id="trait-radar"
            title="How explanations are written"
            caption="Five traits, from the questionnaire and, in the closed-loop arm, from explanation feedback. Further out means more of it: rules before examples, longer explanations, more about why it works, more persistence, more confidence."
            axes={report.radar.traits}
            format={(v) => v.toFixed(2)}
          />
          <Radar
            id="mastery-radar"
            title="Estimated mastery by topic"
            caption="The average estimated mastery of the concepts in each topic. Untouched concepts count at their starting estimate, which depends on their prerequisites."
            axes={report.radar.clusters}
          />
        </div>
      </Section>

      <Section
        id="explainability"
        title="Explainability: why the AI model predicts what it does"
        hint="A neural network predicts the chance of answering the next question correctly. These explanations show which factors drove that prediction, using four methods."
      >
        <div className="rounded-xl border border-primary/20 bg-primary-soft p-5" data-testid="report-summary">
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-primary">In short</p>
          <p className="mt-1.5 text-[15px] leading-relaxed text-fg">{report.summary}</p>
          {failed.length > 0 && (
            <p className="mt-2 text-sm text-muted">
              Not available this time: {failed.map((m) => METHOD_NAME[m.method] ?? m.method).join(", ")}. The rest of the report is complete.
            </p>
          )}
        </div>

        {report.focus === null || report.focus === undefined ? (
          learnerView && (
            <ButtonLink href="/session" size="lg">
              Start learning <span aria-hidden>→</span>
            </ButtonLink>
          )
        ) : (
          <>
            <div className="space-y-2">
              <h3 className="text-sm font-semibold text-fg">The XAI matrix</h3>
              <p className="text-xs text-muted">
                Each factor&apos;s push on the prediction for the latest question ({report.focus.concept}, predicted{" "}
                {Math.round(report.focus.p_correct * 100)}%), according to each method. &quot;Typical&quot; is its average SHAP push across the recent questions.
              </p>
              <XaiMatrix matrix={report.matrix} />
            </div>
            <AgreementAndQuality agreement={report.agreement} quality={report.quality} />
            <div className="grid gap-4 lg:grid-cols-2">
              {report.waterfall && <ShapWaterfall waterfall={report.waterfall} />}
              <LimeBars matrix={report.matrix} r2={report.quality.lime_r2} />
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              <ShapVsLime matrix={report.matrix} />
              {report.counterfactuals && <CounterfactualTable table={report.counterfactuals} />}
            </div>
          </>
        )}
        {report.decision && <DecisionPlot decision={report.decision} />}
        {report.heatmap && <LrpHeatmap heatmap={report.heatmap} />}
      </Section>

      <p className="text-xs text-subtle">
        {report.model.architecture}. Trained on {report.model.trained_on}. On learners it never saw: AUC {report.model.test_auc.toFixed(2)} (BKT{" "}
        {report.model.bkt_auc.toFixed(2)}). It predicts and explains; it does not choose questions.{" "}
        <Link href="/model" className="no-print font-medium text-primary hover:text-primary-hover">
          How the model works →
        </Link>
      </p>
    </div>
  );
}

/** The report's shape while it loads. */
export function ReportSkeleton() {
  const bar = "animate-pulse rounded bg-surface-2";
  return (
    <div className="space-y-8" aria-busy role="status" aria-label="Loading the report">
      <div className={`h-8 w-64 ${bar}`} />
      <div className={`h-16 ${bar}`} />
      <div className="grid gap-4 lg:grid-cols-2">
        <div className={`h-80 ${bar}`} />
        <div className={`h-80 ${bar}`} />
      </div>
      <div className={`h-64 ${bar}`} />
    </div>
  );
}
