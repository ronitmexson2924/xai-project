/**
 * The API answers 503 SERVER_BUSY (with Retry-After) when too many explanations are being worked
 * out at once, e.g. a whole class opening their reports together. Reads are safe to repeat, so
 * the client waits and tries again a few times before showing an error. The wait is spread
 * randomly (half to one and a half times Retry-After) so a class does not come back all at once.
 */
export const BUSY_RETRIES = 3;

/** Milliseconds to wait before trying again, or null to give up. */
export function busyRetryDelay(
  method: string,
  status: number,
  code: string | undefined,
  retryAfter: string | null,
  attempt: number,
  random: () => number = Math.random
): number | null {
  if (method !== "GET" || status !== 503 || code !== "SERVER_BUSY" || attempt >= BUSY_RETRIES) return null;
  const seconds = Math.min(10, Math.max(1, Number(retryAfter) || 5));
  return Math.round(seconds * 1000 * (0.5 + random()));
}
