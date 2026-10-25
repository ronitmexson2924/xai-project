"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import React from "react";
import { useAuth } from "@/lib/auth-context";

const LINKS = [
  { href: "/session", label: "Learn" },
  { href: "/dashboard", label: "My progress" },
  { href: "/tests", label: "Tests" },
];

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b border-white/10 bg-slate-950/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-8">
          <Link href="/" className="flex items-center gap-2">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-indigo-500 to-emerald-400 text-white font-black">
              Ψ
            </span>
            <span className="text-sm font-bold tracking-tight text-white">DSA Learning Engine</span>
          </Link>
          {user?.consent_at && (
            <nav className="hidden md:flex items-center gap-1" aria-label="Main">
              {[...LINKS, ...(user.is_admin ? [{ href: "/admin", label: "Admin" }] : [])].map((l) => (
                <Link
                  key={l.href}
                  href={l.href}
                  aria-current={pathname === l.href ? "page" : undefined}
                  className={`px-3 py-1.5 text-xs font-semibold rounded-lg ${
                    pathname === l.href ? "bg-indigo-600 text-white" : "text-slate-300 hover:text-white hover:bg-slate-800/60"
                  }`}
                >
                  {l.label}
                </Link>
              ))}
            </nav>
          )}
        </div>
        {user ? (
          <div className="flex items-center gap-3">
            <span className="hidden sm:inline text-xs text-slate-300" data-testid="nav-user">
              {user.display_name}
            </span>
            <button
              type="button"
              onClick={handleLogout}
              className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-slate-800 text-slate-200 hover:bg-slate-700"
            >
              Log out
            </button>
          </div>
        ) : (
          <Link href="/login" className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-indigo-600 text-white">
            Log in
          </Link>
        )}
      </div>
    </header>
  );
}
