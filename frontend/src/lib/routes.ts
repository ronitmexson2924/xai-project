import type { UserResponse } from "./api";

/** Where a signed-in user belongs: onboarding until consent + questionnaire are done. */
export function homeFor(user: UserResponse): string {
  if (user.is_admin && !user.consent_at) return "/admin";
  if (!user.consent_at || !user.onboarded) return "/onboarding";
  return "/dashboard";
}
