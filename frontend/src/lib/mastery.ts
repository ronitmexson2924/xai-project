/** Mastery bands, using the planner's own thresholds (backend/app/planner/policy.py). */
export const PREREQ_WEAK = 0.6;
export const FRONTIER_PREREQ_MIN = 0.85;
export const MASTERED = 0.95;

export type Band = "new" | "learning" | "progress" | "ready" | "mastered";

export function band(p: number, attempts: number): Band {
  if (attempts === 0) return "new";
  if (p >= MASTERED) return "mastered";
  if (p >= FRONTIER_PREREQ_MIN) return "ready";
  if (p >= PREREQ_WEAK) return "progress";
  return "learning";
}

export const BAND_LABEL: Record<Band, string> = {
  new: "Not started",
  learning: "Learning",
  progress: "Getting there",
  ready: "Ready to move on",
  mastered: "Mastered",
};

export const CLUSTER_LABEL: Record<string, string> = {
  basics: "Basics",
  "arrays-strings": "Arrays & strings",
  "linked-structures": "Linked structures",
  recursion: "Recursion",
  "sorting-searching": "Sorting & searching",
  trees: "Trees",
  graphs: "Graphs",
  dp: "Dynamic programming",
};
