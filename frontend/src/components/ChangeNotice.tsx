import React from "react";
import type { ChangeNotice as ChangeNoticeData } from "@/lib/api";

/** XAI E5: what the learner's answer or feedback just changed, in their own words. */
export function ChangeNotice({ notice }: { notice: ChangeNoticeData | null | undefined }) {
  if (!notice || notice.messages.length === 0) return null;
  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="change-notice"
      className="rounded-2xl border border-indigo-500/30 bg-indigo-950/40 p-4 text-xs text-indigo-100 space-y-1.5"
    >
      <div className="font-semibold text-indigo-300">What this changed</div>
      <ul className="list-disc pl-5 space-y-1">
        {notice.messages.map((m, i) => (
          <li key={i}>{m}</li>
        ))}
      </ul>
    </div>
  );
}
