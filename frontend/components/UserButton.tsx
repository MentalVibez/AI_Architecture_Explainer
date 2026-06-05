"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";

interface GitHubUser {
  github_id: number;
  login: string;
  name: string | null;
  avatar_url: string | null;
}

export default function UserButton() {
  const [user, setUser] = useState<GitHubUser | null | "loading">("loading");
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const firstItemRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    fetch("/api/auth/me")
      .then((r) => (r.ok ? r.json() : null))
      .then(setUser)
      .catch(() => setUser(null));
  }, []);

  // Close on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Escape closes menu and returns focus to trigger
  useEffect(() => {
    if (!open) return;
    function handler(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
      }
    }
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open]);

  // Move focus into menu when it opens
  useEffect(() => {
    if (open) firstItemRef.current?.focus();
  }, [open]);

  async function signOut() {
    await fetch("/api/auth/logout", { method: "POST" });
    setUser(null);
    setOpen(false);
  }

  if (user === "loading") return null;

  if (!user) {
    return (
      <a
        href="/api/auth/login"
        className="rounded-full border border-white/15 bg-white/[0.04] px-3 py-1.5 font-mono text-[11px] tracking-[0.18em] text-[#9fb0cf] hover:border-[#4d7cff]/40 hover:bg-[#4d7cff]/10 hover:text-white transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#4d7cff]"
      >
        Sign in ↗
      </a>
    );
  }

  const initials = (user.name ?? user.login).slice(0, 2).toUpperCase();

  return (
    <div className="relative" ref={menuRef}>
      <button
        ref={triggerRef}
        onClick={() => setOpen((o) => !o)}
        aria-label={`Signed in as ${user.login} — open account menu`}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-controls="user-account-menu"
        className="flex items-center gap-2 rounded-full border border-white/15 bg-white/[0.04] py-1 pl-1 pr-3 hover:border-white/25 hover:bg-white/[0.07] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#4d7cff]"
      >
        {user.avatar_url ? (
          <Image
            src={user.avatar_url}
            alt=""
            width={24}
            height={24}
            className="rounded-full"
            unoptimized
          />
        ) : (
          <span
            aria-hidden="true"
            className="flex h-6 w-6 items-center justify-center rounded-full bg-[#4d7cff]/30 font-mono text-[9px] text-[#a9c2ff]"
          >
            {initials}
          </span>
        )}
        <span className="font-mono text-[11px] tracking-[0.12em] text-[#c2d3f2]">
          {user.login}
        </span>
      </button>

      {open && (
        <div
          id="user-account-menu"
          role="menu"
          aria-label="Account options"
          className="absolute right-0 top-full mt-2 w-48 rounded-2xl border border-white/10 bg-[#0d1928] py-1 shadow-xl"
        >
          <div className="border-b border-white/8 px-4 py-2.5" aria-hidden="true">
            <p className="text-xs font-medium text-white/80">{user.name ?? user.login}</p>
            <p className="font-mono text-[10px] text-white/40">@{user.login}</p>
          </div>
          <button
            ref={firstItemRef}
            role="menuitem"
            onClick={signOut}
            className="w-full px-4 py-2.5 text-left font-mono text-[11px] tracking-wide text-[#c2d3f2] hover:bg-white/[0.04] hover:text-white transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#4d7cff]"
          >
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
