"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Leaderboard" },
  { href: "/compare", label: "Compare" },
  // Provenance is reached from the methodology page, which carries the same
  // facts; four items do not fit the header at 375px.
  { href: "/methodology", label: "Methodology" },
];

export function Nav() {
  const pathname = usePathname();
  return (
    <nav className="flex gap-4 text-[13px]">
      {LINKS.map(({ href, label }) => {
        const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={active ? "text-text" : "text-muted hover:text-text"}
          >
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
