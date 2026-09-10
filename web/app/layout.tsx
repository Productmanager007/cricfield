import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import "@fontsource-variable/inter";
import { LimitationsNote } from "@/components/LimitationsNote";
import { Nav } from "@/components/Nav";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "cricfield", template: "%s · cricfield" },
  description: "Fielding runs above average for IPL fielders, from ball-by-ball data.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en-GB">
      <body className="min-h-screen bg-bg font-sans text-text antialiased">
        <header className="border-b border-border">
          <div className="mx-auto flex h-11 max-w-5xl items-center gap-6 px-4 sm:px-6">
            <Link href="/" className="text-sm font-semibold tracking-tight text-amber">
              cricfield
            </Link>
            <Nav />
          </div>
        </header>
        <LimitationsNote />
        {children}
      </body>
    </html>
  );
}
