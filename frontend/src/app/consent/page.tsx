"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

/** Consent is now the first step of onboarding. */
export default function ConsentRedirect() {
  const router = useRouter();
  useEffect(() => router.replace("/onboarding"), [router]);
  return null;
}
