"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import Logo from "@/components/Logo";

export default function Nav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const links = [
    { href: "/", label: "Atlas" },
    { href: "/scout", label: "Scout" },
    { href: "/map", label: "Map" },
    { href: "/review", label: "Review" },
  ];

  return (
    <nav className="sticky top-0 z-50 border-b border-white/10 bg-[#08111f]/80 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
        <Link
          href="/"
          className="flex items-center gap-2.5 group"
          aria-label="CodebaseAtlas home"
        >
          <Logo size={20} />
          <div className="flex flex-col leading-none">
            <span className="font-sans font-semibold text-[13px] text-[#f3f7ff] tracking-tight select-none group-hover:text-white">
              CodebaseAtlas
            </span>
            <span className="font-mono text-[9px] uppercase tracking-[0.24em] text-[#6d7f9f]">
              Code Understanding
            </span>
          </div>
        </Link>

        <div className="hidden sm:flex items-center gap-3">
          <div className="rounded-full border border-white/10 bg-white/[0.03] p-1">
            <div className="flex items-center gap-1">
              {links.map(({ href, label }) => (
                <NavLink key={href} href={href} label={label} active={pathname === href} />
              ))}
            </div>
          </div>
          <NavLink href="/pricing" label="Pricing" active={pathname === "/pricing"} />
          <NavLink href="/how-it-works" label="Docs" active={pathname === "/how-it-works"} />
          <a
            href="https://github.com/MentalVibez/AI_Architecture_Explainer"
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-full border border-white/10 px-3 py-1.5 text-[11px] font-mono tracking-[0.18em] text-[#9fb0cf] hover:border-[#4d7cff]/40 hover:bg-white/[0.03] hover:text-white"
            aria-label="GitHub"
          >
            GitHub ↗
          </a>
        </div>

        <button
          className="sm:hidden flex flex-col justify-center gap-[5px] w-8 h-8 shrink-0"
          onClick={() => setOpen((o) => !o)}
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
        >
          <span className={`block h-px bg-[#9fb0cf] transition-all duration-200 origin-center
                           ${open ? "rotate-45 translate-y-[6px]" : ""}`} />
          <span className={`block h-px bg-[#9fb0cf] transition-all duration-200
                           ${open ? "opacity-0" : ""}`} />
          <span className={`block h-px bg-[#9fb0cf] transition-all duration-200 origin-center
                           ${open ? "-rotate-45 -translate-y-[6px]" : ""}`} />
        </button>
      </div>

      {open && (
        <div className="sm:hidden border-t border-white/10 bg-[#08111f]/95">
          <div className="max-w-7xl mx-auto px-6 py-4 flex flex-col gap-1">
            {[...links, { href: "/pricing", label: "Pricing" }, { href: "/how-it-works", label: "Docs" }].map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                onClick={() => setOpen(false)}
                className={`px-3 py-2.5 font-mono text-[12px] tracking-widest uppercase rounded-xl
                            transition-colors
                            ${pathname === href
                              ? "text-white bg-[#4d7cff]/15 border border-[#4d7cff]/30"
                              : "text-[#9fb0cf] hover:text-white hover:bg-white/[0.04] border border-transparent"
                            }`}
                aria-current={pathname === href ? "page" : undefined}
              >
                {label}
              </Link>
            ))}
            <a
              href="https://github.com/MentalVibez/AI_Architecture_Explainer"
              target="_blank"
              rel="noopener noreferrer"
              className="px-3 py-2.5 font-mono text-[12px] tracking-widest text-[#9fb0cf]
                         hover:text-white transition-colors"
            >
              GitHub ↗
            </a>
          </div>
        </div>
      )}
    </nav>
  );
}

function NavLink({
  href,
  label,
  active,
}: {
  href: string;
  label: string;
  active: boolean;
}) {
  return (
    <Link
      href={href}
      className={`px-3 py-1.5 font-mono text-[11px] tracking-[0.18em] rounded-full
                 transition-all duration-150 uppercase border
                 ${active
                   ? "text-white border-[#4d7cff]/40 bg-[#4d7cff]/14 shadow-[0_8px_22px_rgba(77,124,255,0.16)]"
                   : "text-[#9fb0cf] border-transparent hover:text-white hover:border-white/10 hover:bg-white/[0.03]"
                 }`}
      aria-current={active ? "page" : undefined}
    >
      {label}
    </Link>
  );
}
