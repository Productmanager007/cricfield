import Link from "next/link";
import { Fragment } from "react";
import { readLimitationsEvidence } from "@/lib/limitations";

// MILESTONE Phase 2. Always on screen wherever a number is: not a modal, not a
// tooltip, not behind a link. Rendered from the root layout so no route can
// omit it, and into the static HTML so it shows before any data has loaded.
export function LimitationsNote() {
  const { evidence, of } = readLimitationsEvidence();
  return (
    <aside aria-label="Limitations of this model" className="border-b border-border bg-panel">
      <div className="mx-auto flex max-w-5xl flex-col gap-0.5 px-4 py-2.5 sm:flex-row sm:gap-4 sm:px-6">
        <p className="shrink-0 text-[11px] font-semibold uppercase leading-5 tracking-wider text-amber">Limitations</p>
        <p className="text-[13px] leading-5 text-muted">
          <strong className="font-medium text-text">This model sees only fielding that ends in a wicket.</strong>{" "}
          Misfields, boundary saves, dropped catches and diving stops are not in the source data. Elite ground
          fielders rank far below their reputation —{" "}
          {evidence.map((e, i) => (
            <Fragment key={e.player}>
              {i > 0 && " and "}
              {e.player}
              {i === 0 ? " is " : " "}
              <span className="tabular-nums text-text">
                {ordinal(e.rank)}
                {i === 0 && ` of ${of}`}
              </span>
            </Fragment>
          ))}
          .{" "}
          {/* On every route, so every page that shows a number links to the methodology. */}
          <Link href="/methodology" className="whitespace-nowrap text-amber hover:underline">
            Read the methodology →
          </Link>
        </p>
      </div>
    </aside>
  );
}

export function ordinal(n: number): string {
  const teen = n % 100 >= 11 && n % 100 <= 13;
  return `${n}${teen ? "th" : (["th", "st", "nd", "rd"][n % 10] ?? "th")}`;
}
