/**
 * The engagement extras: a personal greeting, warmer result moments, "you beat the prediction",
 * the animated mastery meter, the session strip and recap, and the second-person model panel.
 *
 * One switch, compiled in at build time (NEXT_PUBLIC_ENGAGEMENT_UI=true). Off by default, so a
 * study can keep every arm on the same, plain app: with it off the learner sees the same screens and
 * copy as before (apart from fixes that apply to everyone). Nothing behind it changes what the
 * backend computes or records.
 */
export const ENGAGEMENT_UI = process.env.NEXT_PUBLIC_ENGAGEMENT_UI === "true";

/** Questions per session before the recap card offers a break. */
export const RECAP_EVERY = Math.max(1, Number(process.env.NEXT_PUBLIC_RECAP_EVERY) || 5);
