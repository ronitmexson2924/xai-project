"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "motion/react";
import React, { useEffect, useState } from "react";
import { Button } from "./ui/Button";
import { Field } from "./ui/Field";
import { Logo } from "./ui/Logo";
import { ease } from "./ui/motion";
import { ApiException, useAuth } from "@/lib/auth-context";
import { ENGAGEMENT_UI } from "@/lib/engagement";
import { firstName } from "@/lib/moments";
import { homeFor } from "@/lib/routes";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  const { user, isLoading, login, register } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [touched, setTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [welcome, setWelcome] = useState<string | null>(null);
  const signup = mode === "signup";

  useEffect(() => {
    if (!isLoading && user && welcome === null) router.replace(homeFor(user));
  }, [user, isLoading, router, welcome]);

  const errors = {
    name: signup && !name.trim() ? "Tell us what to call you" : null,
    email: !EMAIL.test(email.trim()) ? "Enter a valid email address" : null,
    password:
      signup && password.length < 8
        ? "Use at least 8 characters"
        : !signup && !password
          ? "Enter your password"
          : null,
  };
  const valid = !errors.name && !errors.email && !errors.password;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setTouched(true);
    setError(null);
    if (!valid) return;
    setBusy(true);
    try {
      const u = signup
        ? await register({ email: email.trim(), password, display_name: name.trim() })
        : await login({ email: email.trim(), password });
      // greet by name while the next page loads; the redirect is not held back for it
      if (ENGAGEMENT_UI && !signup) setWelcome(firstName(u.display_name));
      router.replace(homeFor(u));
    } catch (err) {
      setError(err instanceof ApiException ? err.message : "Something went wrong. Please try again.");
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col bg-bg">
      <header className="mx-auto flex h-16 w-full max-w-6xl items-center px-4 sm:px-6">
        <Logo />
      </header>
      <main className="flex flex-1 items-center justify-center px-4 pb-16">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease }}
          className="w-full max-w-sm"
        >
          <h1 className="text-2xl font-semibold tracking-tight text-fg" aria-live="polite">
            {signup ? "Create your account" : welcome ? `Welcome back, ${welcome}` : "Welcome back"}
          </h1>
          <p className="mt-1.5 text-sm text-muted">
            {signup ? "It takes a minute. Then a few quick questions and you’re in." : "Log in to pick up where you left off."}
          </p>

          <form onSubmit={submit} noValidate className="mt-8 space-y-4">
            {signup && (
              <Field
                label="Name"
                name="name"
                autoComplete="name"
                placeholder="Ada Lovelace"
                value={name}
                maxLength={100}
                onChange={(e) => setName(e.target.value)}
                error={touched ? errors.name : null}
              />
            )}
            <Field
              label="Email"
              name="email"
              type="email"
              autoComplete="email"
              placeholder="you@university.edu"
              value={email}
              maxLength={254}
              onChange={(e) => setEmail(e.target.value)}
              error={touched ? errors.email : null}
            />
            <Field
              label="Password"
              name="password"
              type="password"
              autoComplete={signup ? "new-password" : "current-password"}
              placeholder={signup ? "At least 8 characters" : "Your password"}
              value={password}
              maxLength={72}
              onChange={(e) => setPassword(e.target.value)}
              hint={signup ? "8 or more characters. A short sentence works well." : undefined}
              error={touched ? errors.password : null}
            />

            {error && (
              <motion.p
                role="alert"
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger"
              >
                {error}
              </motion.p>
            )}

            <Button type="submit" size="lg" className="w-full" loading={busy}>
              {signup ? "Create account" : "Log in"}
            </Button>
          </form>

          <p className="mt-6 text-center text-sm text-muted">
            {signup ? "Already have an account? " : "New here? "}
            <Link href={signup ? "/login" : "/signup"} className="font-medium text-primary hover:text-primary-hover">
              {signup ? "Log in" : "Create an account"}
            </Link>
          </p>
        </motion.div>
      </main>
    </div>
  );
}
