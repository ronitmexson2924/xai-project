"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import React, { useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { Logo } from "./ui/Logo";
import { cn } from "./ui/cn";

const LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/session", label: "Learn" },
  { href: "/tests", label: "Tests" },
];

/** Signed-in layout: a quiet top bar, the page, nothing else. */
export function AppShell({ children, wide = false }: { children: React.ReactNode; wide?: boolean }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const [menu, setMenu] = useState(false);
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
            <nav aria-label="Main" className="hidden items-center gap-1 sm:flex">
              {links.map((l) => {
                const active = pathname === l.href || (l.href !== "/dashboard" && pathname.startsWith(l.href));
                return (
                  <Link
                    key={l.href}
                    href={l.href}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "relative rounded-md px-3 py-1.5 text-sm transition-colors",
                      active ? "text-fg" : "text-muted hover:text-fg"
                    )}
                  >
                    {active && (
                      <motion.span layoutId="nav-pill" className="absolute inset-0 -z-10 rounded-md bg-surface-2" transition={{ type: "spring", stiffness: 400, damping: 34 }} />
                    )}
                    {l.label}
                  </Link>
                );
              })}
            </nav>
          </div>
          {user && (
            <div className="relative" ref={menuRef}>
              <button
                type="button"
                onClick={() => setMenu((m) => !m)}
                aria-haspopup="menu"
                aria-expanded={menu}
                aria-label="Account menu"
                className="flex h-8 w-8 items-center justify-center rounded-full bg-accent-soft text-sm font-semibold text-accent"
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
      <main id="main" className={cn("mx-auto px-4 pb-24 pt-8 sm:px-6 sm:py-10", wide ? "max-w-7xl" : "max-w-6xl")}>
        {children}
      </main>
      {links.length > 0 && (
        <nav
          aria-label="Main"
          className="fixed inset-x-0 bottom-0 z-40 flex border-t border-line bg-bg/90 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl sm:hidden"
        >
          {links.map((l) => {
            const active = pathname === l.href || (l.href !== "/dashboard" && pathname.startsWith(l.href));
            return (
              <Link
                key={l.href}
                href={l.href}
                aria-current={active ? "page" : undefined}
                className={cn("flex flex-1 flex-col items-center gap-1 py-2.5 text-xs", active ? "text-accent" : "text-muted")}
              >
                <span className={cn("h-1 w-1 rounded-full", active ? "bg-accent" : "bg-transparent")} aria-hidden />
                {l.label}
              </Link>
            );
          })}
        </nav>
      )}
    </div>
  );
}

export function PageLoading() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center" role="status" aria-label="Loading">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-accent border-r-transparent" />
    </div>
  );
}
