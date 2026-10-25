"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "./auth-context";

/**
 * Send visitors to the step they still need: login, then consent. Returns true once the page
 * may render its content.
 */
export function useLearnerGuard(options: { requireConsent?: boolean; requireAdmin?: boolean } = {}) {
  const { requireConsent = true, requireAdmin = false } = options;
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;
    if (!user) router.replace("/login");
    else if (requireAdmin && !user.is_admin) router.replace("/");
    else if (requireConsent && !requireAdmin && !user.consent_at) router.replace("/consent");
  }, [user, isLoading, requireConsent, requireAdmin, router]);

  if (isLoading || !user) return false;
  if (requireAdmin) return Boolean(user.is_admin);
  return !requireConsent || Boolean(user.consent_at);
}
