"use client";

import { usePathname } from "next/navigation";
import { useState } from "react";
import Logo from "@/components/Logo";

export default function Nav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const links = [
    { href: "/",       label: "01 / Atlas"  },
    { href: "/scout",  label: "02 / Scout"  },
    { href: "/map",    label: "03 / Map"    },
    { href: "/review", label: "04 / Review" },
  ];

  return (
    <nav className="border-b border-[#1e1e1e] bg-[#0f0f0f]/95 backdrop-blur-sm sticky top-0 z-50">
      <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">

        {/* Wordmark */}
        <a
          href="/"
          className="flex items-center gap-2.5 group"
          aria-label="CodebaseAtlas home"
        >
          <Logo size={20} />
          <span className="font-sans font-medium text-[13px] text-[#e8e0d4] tracking-tight select-none
                           group-hover:text-white transition-colors">
            CodebaseAtlas
          </span>
        </a>

        {/* Desktop tool links */}
        <div className="hidden sm:flex items-center gap-1">
          {links.map(({ href, label }) => (
            <NavLink key={href} href={href} label={label} active={pathname === href} />
          ))}
          <NavLink href="/pricing" label="Pricing" active={pathname === "/pricing"} />
          <NavLink href="/how-it-works" label="Docs" active={pathname === "/how-it-works"} />
          <a
            href="https://github.com/MentalVibez/AI_Architecture_Explainer"
            target="_blank"
            rel="noopener noreferrer"
            className="ml-3 text-[11px] font-mono tracking-widest text-[#3a3a3a] hover:text-[#5a5a5a] transition-colors"
            aria-label="GitHub"
          >
            GH ↗
          </a>
        </div>

        {/* Mobile hamburger */}
        <button
          className="sm:hidden flex flex-col justify-center gap-[5px] w-8 h-8 shrink-0"
          onClick={() => setOpen((o) => !o)}
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
        >
          <span className={`block h-px bg-[#4a4a4a] transition-all duration-200 origin-center
                           ${open ? "rotate-45 translate-y-[6px]" : ""}`} />
          <span className={`block h-px bg-[#4a4a4a] transition-all duration-200
                           ${open ? "opacity-0" : ""}`} />
          <span className={`block h-px bg-[#4a4a4a] transition-all duration-200 origin-center
                           ${open ? "-rotate-45 -translate-y-[6px]" : ""}`} />
        </button>
      </div>

      {/* Mobile menu */}
      {open && (
        <div className="sm:hidden border-t border-[#1a1a1a] bg-[#0f0f0f]">
          <div className="max-w-6xl mx-auto px-6 py-4 flex flex-col gap-1">
            {[...links, { href: "/pricing", label: "Pricing" }, { href: "/how-it-works", label: "Docs" }].map(({ href, label }) => (
              <a
                key={href}
                href={href}
                onClick={() => setOpen(false)}
                className={`px-3 py-2.5 font-mono text-[12px] tracking-widest uppercase rounded
                            transition-colors
                            ${pathname === href
                              ? "text-[#c8a96e] bg-[#c8a96e]/8"
                              : "text-[#4a4a4a] hover:text-[#c8a96e] hover:bg-[#c8a96e]/5"
                            }`}
                aria-current={pathname === href ? "page" : undefined}
              >
                {label}
              </a>
            ))}
            <a
              href="https://github.com/MentalVibez/AI_Architecture_Explainer"
              target="_blank"
              rel="noopener noreferrer"
              className="px-3 py-2.5 font-mono text-[12px] tracking-widest text-[#3a3a3a]
                         hover:text-[#5a5a5a] transition-colors"
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
    <a
      href={href}
      className={`px-3 py-1.5 font-mono text-[11px] tracking-widest rounded
                 transition-all duration-150 uppercase
                 ${active
                   ? "text-[#c8a96e] bg-[#c8a96e]/8"
                   : "text-[#4a4a4a] hover:text-[#c8a96e] hover:bg-[#c8a96e]/5"
                 }`}
      aria-current={active ? "page" : undefined}
    >
      {label}
    </a>
  );
}
