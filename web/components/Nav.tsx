"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Leaderboard" },
  { href: "/compare", label: "Compare" },
  { href: "/provenance", label: "Provenance" },
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
