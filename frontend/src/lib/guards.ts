"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "./auth-context";
import { homeFor } from "./routes";

type Need = "learner" | "onboarding" | "admin";

/**
 * Keep each page to the users it is for. "learner": signed in, consented and onboarded;
 * "onboarding": signed in (consent and questionnaire still to do); "admin": an admin account.
 * Returns true once the page may render its content.
 */
export function useLearnerGuard(options: { need?: Need; requireAdmin?: boolean; requireConsent?: boolean } = {}) {
  const need: Need = options.requireAdmin ? "admin" : options.requireConsent === false ? "onboarding" : (options.need ?? "learner");
  const { user, isLoading, signedOut } = useAuth();
  const router = useRouter();

  const allowed =
    !!user &&
    (need === "admin" ? user.is_admin : need === "onboarding" ? true : !!user.consent_at && !!user.onboarded);

  useEffect(() => {
    if (isLoading) return;
    if (!user) router.replace(signedOut ? "/" : "/login");
    else if (!allowed) router.replace(homeFor(user));
  }, [user, isLoading, signedOut, allowed, router]);

  return !isLoading && allowed;
}
