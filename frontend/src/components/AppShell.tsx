"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import React, { useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { ENGAGEMENT_UI } from "@/lib/engagement";
import { avatarHue } from "@/lib/moments";
import { getTheme, setTheme, ThemeChoice } from "@/lib/theme";
import { Logo } from "./ui/Logo";
import { cn } from "./ui/cn";

const LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/session", label: "Learn" },
  { href: "/report", label: "Report" },
  { href: "/tests", label: "Tests" },
  { href: "/model", label: "Model" },
];

const THEMES: { value: ThemeChoice; label: string }[] = [
  { value: "system", label: "System" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

/**
 * Signed-in layout: a quiet top bar, the page, nothing else. `actions` (e.g. Continue) sit in a
 * bar fixed to the bottom of the screen, above the phone tab bar, so they never cover content.
 */
export function AppShell({ children, wide = false, actions }: { children: React.ReactNode; wide?: boolean; actions?: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const [menu, setMenu] = useState(false);
  const [theme, setThemeChoice] = useState<ThemeChoice>("system");
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenu(false);
    };
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setMenu(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", esc);
    };
  }, []);

  const links = [...(user?.onboarded ? LINKS : []), ...(user?.is_admin ? [{ href: "/admin", label: "Admin" }] : [])];
  const initial = (user?.display_name || "?").trim().charAt(0).toUpperCase();
  const hue = ENGAGEMENT_UI && user ? avatarHue(user.display_name) : null;

  const toggleMenu = () => {
    if (!menu) setThemeChoice(getTheme());
    setMenu((m) => !m);
  };
  const chooseTheme = (choice: ThemeChoice) => {
    setTheme(choice);
    setThemeChoice(choice);
  };

  const signOut = async () => {
    setMenu(false);
    await logout();
    router.push("/");
  };

  return (
    <div className="min-h-screen bg-bg">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-surface focus:px-3 focus:py-2 focus:shadow-pop">
        Skip to content
      </a>
      <header className="sticky top-0 z-40 border-b border-line bg-bg/80 backdrop-blur-xl">
        <div className={cn("mx-auto flex h-14 items-center justify-between gap-4 px-4 sm:px-6", wide ? "max-w-7xl" : "max-w-6xl")}>
          <div className="flex min-w-0 items-center gap-6">
            <Logo href={user?.onboarded ? "/dashboard" : "/"} />
            <nav aria-label="Main" className="hidden items-center sm:flex">
              {links.map((l) => {
                const active = pathname === l.href || (l.href !== "/dashboard" && pathname.startsWith(l.href));
                return (
                  <Link
                    key={l.href}
                    href={l.href}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "relative flex h-14 items-center px-3 text-sm transition-colors",
                      active ? "font-medium text-primary" : "text-muted hover:text-fg"
                    )}
                  >
                    {l.label}
                    {active && (
                      <motion.span
                        layoutId="nav-underline"
                        className="absolute inset-x-3 -bottom-px h-0.5 rounded-full bg-primary"
                        transition={{ type: "spring", stiffness: 400, damping: 34 }}
                      />
                    )}
                  </Link>
                );
              })}
            </nav>
          </div>
          {user && (
            <div className="relative" ref={menuRef}>
              <button
                type="button"
                onClick={toggleMenu}
                aria-haspopup="menu"
                aria-expanded={menu}
                aria-label="Account menu"
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-full text-sm font-semibold",
                  hue === null ? "bg-primary-soft text-primary" : "avatar-hue"
                )}
                style={hue === null ? undefined : ({ "--hue": hue } as React.CSSProperties)}
                data-testid="nav-user"
                title={user.display_name}
              >
                {initial}
              </button>
              <AnimatePresence>
                {menu && (
                  <motion.div
                    role="menu"
                    initial={{ opacity: 0, y: -6, scale: 0.98 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -6, scale: 0.98 }}
                    transition={{ duration: 0.15 }}
                    className="absolute right-0 mt-2 w-60 origin-top-right rounded-xl border border-line bg-surface p-1.5 shadow-pop"
                  >
                    <div className="px-3 py-2">
                      <p className="truncate text-sm font-medium text-fg">{user.display_name}</p>
                      <p className="truncate text-xs text-subtle">{user.email}</p>
                    </div>
                    <div className="my-1 h-px bg-line" />
                    {user.onboarded && (
                      <Link role="menuitem" href="/account" onClick={() => setMenu(false)} className="block rounded-lg px-3 py-2 text-sm text-muted hover:bg-surface-2 hover:text-fg">
                        Account &amp; privacy
                      </Link>
                    )}
                    <div className="px-3 py-2">
                      <p id="theme-label" className="label-caps">
                        Theme
                      </p>
                      <div role="group" aria-labelledby="theme-label" className="mt-1.5 grid grid-cols-3 rounded-lg border border-line bg-surface-2 p-0.5">
                        {THEMES.map((t) => (
                          <button
                            key={t.value}
                            type="button"
                            role="menuitemradio"
                            aria-checked={theme === t.value}
                            onClick={() => chooseTheme(t.value)}
                            className={cn(
                              "rounded-md px-2 py-1 text-xs font-medium transition-colors",
                              theme === t.value ? "bg-surface text-fg shadow-card" : "text-muted hover:text-fg"
                            )}
                          >
                            {t.label}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div className="my-1 h-px bg-line" />
                    <button role="menuitem" type="button" onClick={signOut} className="w-full rounded-lg px-3 py-2 text-left text-sm text-muted hover:bg-surface-2 hover:text-fg">
                      Log out
                    </button>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )}
        </div>
      </header>
      <main
        id="main"
        className={cn("mx-auto px-4 pt-8 sm:px-6 sm:pt-10", actions ? "pb-44 sm:pb-28" : "pb-24 sm:pb-10", wide ? "max-w-7xl" : "max-w-6xl")}
      >
        {children}
      </main>
      <div className="fixed inset-x-0 bottom-0 z-40">
        {actions && (
          <div className="border-t border-line bg-bg/85 backdrop-blur-xl" data-testid="action-bar">
            <div className="mx-auto flex max-w-3xl items-center justify-end gap-3 px-4 py-3 sm:px-6">{actions}</div>
          </div>
        )}
        {links.length > 0 && (
          <nav
            aria-label="Main"
            className="flex border-t border-line bg-bg/90 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl sm:hidden"
          >
            {links.map((l) => {
              const active = pathname === l.href || (l.href !== "/dashboard" && pathname.startsWith(l.href));
              return (
                <Link
                  key={l.href}
                  href={l.href}
                  aria-current={active ? "page" : undefined}
                  className={cn("flex flex-1 flex-col items-center gap-1 py-2.5 text-xs", active ? "text-primary" : "text-muted")}
                >
                  <span className={cn("h-1 w-1 rounded-full", active ? "bg-primary" : "bg-transparent")} aria-hidden />
                  {l.label}
                </Link>
              );
            })}
          </nav>
        )}
      </div>
    </div>
  );
}

export function PageLoading() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center" role="status" aria-label="Loading">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-primary border-r-transparent" />
    </div>
  );
}
